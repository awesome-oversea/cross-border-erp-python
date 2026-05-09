import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from time import perf_counter

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles

from erp.bootstrap.config import get_settings
from erp.shared.context import actor_id_var, actor_type_var, tenant_id_var, trace_id_var
from erp.shared.db.session import close_db, init_db_engine
from erp.shared.exceptions import BizException, Result
from erp.shared.observability.logging import get_logger, setup_logging
from erp.shared.observability.metrics import setup_metrics_middleware
from erp.shared.observability.tracing import setup_tracing


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    init_db_engine(settings.db)
    logger = get_logger("erp.main")
    logger.info("erp_startup", environment=settings.environment)
    from erp.shared.events.handlers import register_cross_domain_handlers
    register_cross_domain_handlers()
    yield
    await close_db()
    logger.info("erp_shutdown")


def _clone_legacy_domain_router(router, domain_prefix: str) -> APIRouter:
    legacy_router = APIRouter(prefix=f"/{domain_prefix}/api/out/v1", tags=list(router.tags))
    router_prefix = getattr(router, "prefix", "") or ""
    for route in router.routes:
        if not isinstance(route, APIRoute):
            continue
        legacy_path = route.path
        if router_prefix and legacy_path.startswith(router_prefix):
            legacy_path = legacy_path[len(router_prefix):] or "/"
        legacy_router.add_api_route(
            legacy_path,
            route.endpoint,
            methods=list(route.methods or []),
            response_model=route.response_model,
            status_code=route.status_code,
            tags=route.tags,
            summary=route.summary,
            description=route.description,
            response_description=route.response_description,
            responses=route.responses,
            deprecated=route.deprecated,
            operation_id=route.operation_id,
            response_model_include=route.response_model_include,
            response_model_exclude=route.response_model_exclude,
            response_model_by_alias=route.response_model_by_alias,
            response_model_exclude_unset=route.response_model_exclude_unset,
            response_model_exclude_defaults=route.response_model_exclude_defaults,
            response_model_exclude_none=route.response_model_exclude_none,
            include_in_schema=False,
            name=route.name,
            openapi_extra=route.openapi_extra,
        )
    return legacy_router


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(level="DEBUG" if settings.debug else "INFO", json_logs=settings.environment == "production")
    logger = get_logger("erp.main")

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description=(
            "# 跨境电商ERP API 文档\n\n"
            "## 概述\n"
            "基于 FastAPI + DDD 架构的跨境电商ERP系统，覆盖14个业务领域。\n\n"
            "## 认证方式\n"
            "所有接口需通过 Header 传递租户和用户信息：\n"
            "- `X-Tenant-ID`: 租户ID（必填）\n"
            "- `X-Actor-ID`: 操作者ID（必填）\n"
            "- `X-Actor-Type`: 操作者类型 user/pms（默认 user）\n"
            "- `X-Trace-ID`: 链路追踪ID（自动生成）\n\n"
            "## 业务领域\n"
            "| 域 | 路径前缀 | 说明 |\n"
            "|---|---|---|\n"
            "| IAM | /api/iam/v1 | 组织权限域 |\n"
            "| PDM | /api/pdm/v1 | 产品开发域 |\n"
            "| SOM | /api/som/v1 | 销售运营域 |\n"
            "| OMS | /api/oms/v1 | 订单域 |\n"
            "| SCM | /api/scm/v1 | 供应链域 |\n"
            "| WMS | /api/wms/v1 | 仓储域 |\n"
            "| TMS | /api/tms/v1 | 物流域 |\n"
            "| FMS | /api/fms/v1 | 财务域 |\n"
            "| ADS | /api/ads/v1 | 广告管理域 |\n"
            "| CRM | /api/crm/v1 | 客服售后域 |\n"
            "| FBA | /api/fba/v1 | FBA/海外仓域 |\n"
            "| BI | /api/bi/v1 | 商业智能域 |\n"
            "| Dashboard | /api/dashboard/v1 | 工作台域 |\n"
            "| SYS | /api/sys/v1 | 系统设置域 |\n\n"
            "## 响应格式\n"
            "所有接口统一返回 `{code, message, data, trace_id}` 格式。"
        ),
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=f"{settings.api_prefix}/redoc",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        lifespan=lifespan,
        contact={"name": "ERP Team", "email": "erp-team@example.com"},
        license_info={"name": "Proprietary"},
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def context_middleware(request: Request, call_next):
        start = perf_counter()
        path = request.url.path
        tid = request.headers.get("X-Tenant-ID", "")
        trid = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
        aid = request.headers.get("X-Actor-ID", "")
        atype = request.headers.get("X-Actor-Type", "user")

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer ") and not aid:
            try:
                from erp.modules.iam.domain.auth import decode_token
                payload = decode_token(auth_header[7:])
                aid = payload.get("sub", aid)
                if not tid:
                    tid = payload.get("tenant_id", tid)
                atype = payload.get("actor_type", atype)
            except Exception:
                pass

        tenant_id_var.set(tid)
        trace_id_var.set(trid)
        actor_id_var.set(aid)
        actor_type_var.set(atype)

        exempt_prefixes = (
            settings.admin_prefix,
            settings.open_prefix,
            settings.webhook_prefix,
            f"{settings.api_prefix}/health",
            f"{settings.api_prefix}/docs",
            f"{settings.api_prefix}/redoc",
            f"{settings.api_prefix}/openapi.json",
            f"{settings.api_prefix}/iam/v1/auth",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico",
            "/static",
        )
        exempt_paths = {"/"}

        if path not in exempt_paths and not any(path.startswith(prefix) for prefix in exempt_prefixes):
            if not tid:
                response = JSONResponse(
                    status_code=200,
                    content=Result.fail(code=422, message="X-Tenant-ID header is required", trace_id=trid).__dict__,
                )
                response.headers["X-Trace-ID"] = trid
                return response
            if not aid:
                response = JSONResponse(
                    status_code=200,
                    content=Result.fail(code=422, message="X-Actor-ID header is required", trace_id=trid).__dict__,
                )
                response.headers["X-Trace-ID"] = trid
                return response

        response = await call_next(request)
        response.headers["X-Trace-ID"] = trid
        elapsed = (perf_counter() - start) * 1000
        logger.info(
            "request_completed",
            method=request.method,
            path=path,
            status=response.status_code,
            elapsed_ms=round(elapsed, 2),
        )
        return response

    @app.exception_handler(BizException)
    async def biz_exception_handler(request: Request, exc: BizException):
        return JSONResponse(
            status_code=200,
            content=Result.fail(code=exc.code, message=exc.message, trace_id=trace_id_var.get("")).__dict__,
        )

    setup_metrics_middleware(app)
    setup_tracing(app, service_name=settings.app_name, environment=settings.environment)

    from erp.api.admin.router import admin_router
    from erp.api.openapi.router import open_router
    from erp.api.webhooks.router import webhook_router
    from erp.connectors.router import router as connectors_router
    from erp.middleware.ad_optimization.interfaces.router import router as ad_optimization_router
    from erp.middleware.api_platform.interfaces.router import router as api_platform_router
    from erp.middleware.audit_center.interfaces.router import router as audit_center_router
    from erp.middleware.auth_center.interfaces.router import router as auth_center_router
    from erp.middleware.billing.interfaces.router import router as billing_middleware_router
    from erp.middleware.cdp.interfaces.router import router as cdp_router
    from erp.middleware.compliance.interfaces.router import router as compliance_router
    from erp.middleware.connector_platform.interfaces.router import router as connector_platform_router
    from erp.middleware.content_review.interfaces.router import router as content_review_router
    from erp.middleware.cost_engine.interfaces.router import router as cost_engine_router
    from erp.middleware.file_processor.interfaces.router import router as file_processor_router
    from erp.middleware.forex.interfaces.router import router as forex_router
    from erp.middleware.inventory_voucher.interfaces.router import router as inventory_voucher_router
    from erp.middleware.invoice_tax.interfaces.router import router as invoice_tax_router
    from erp.middleware.logistics_strategy.interfaces.router import router as logistics_strategy_router
    from erp.middleware.masking_center.interfaces.router import router as masking_center_router
    from erp.middleware.notification_center.interfaces.router import router as notification_center_router
    from erp.middleware.order_strategy.interfaces.router import router as order_strategy_router
    from erp.middleware.payment.interfaces.router import router as payment_router
    from erp.middleware.profit_engine.interfaces.router import router as profit_engine_router
    from erp.middleware.selection.interfaces.router import router as selection_router
    from erp.middleware.task_scheduler.interfaces.router import router as task_scheduler_router
    from erp.middleware.translation_center.interfaces.router import router as translation_center_router
    from erp.middleware.workflow_engine.interfaces.router import router as workflow_engine_router
    from erp.modules.ads.interfaces.out_router import router as ads_out_router
    from erp.modules.ads.interfaces.router import router as ads_router
    from erp.modules.ads.interfaces.smart_bid_router import router as ads_smart_bid_router
    from erp.modules.bi.interfaces.alert_router import router as bi_alert_router
    from erp.modules.bi.interfaces.metric_router import router as bi_metric_router
    from erp.modules.bi.interfaces.router import router as bi_router
    from erp.modules.crm.interfaces.lifecycle_router import router as crm_lifecycle_router
    from erp.modules.crm.interfaces.out_router import router as crm_out_router
    from erp.modules.crm.interfaces.router import router as crm_router
    from erp.modules.dashboard.interfaces.router import router as dashboard_router
    from erp.modules.fba.interfaces.router import router as fba_router
    from erp.modules.fms.interfaces.billing_strategy_router import router as billing_strategy_router
    from erp.modules.fms.interfaces.cost_profit_router import router as cost_profit_router
    from erp.modules.fms.interfaces.out_router import router as fms_out_router
    from erp.modules.fms.interfaces.router import router as fms_router
    from erp.modules.fms.interfaces.voucher_router import router as voucher_router
    from erp.modules.iam.interfaces.router import iam_router
    from erp.modules.oms.interfaces.out_router import router as oms_out_router
    from erp.modules.oms.interfaces.router import router as oms_router
    from erp.modules.oms.interfaces.strategy_router import router as oms_strategy_router
    from erp.modules.pdm.interfaces.out_router import router as pdm_out_router
    from erp.modules.pdm.interfaces.router import router as pdm_router
    from erp.modules.scm.interfaces.out_router import router as scm_out_router
    from erp.modules.scm.interfaces.router import router as scm_router
    from erp.modules.som.interfaces.out_router import router as som_out_router
    from erp.modules.som.interfaces.router import router as som_router
    from erp.modules.sys.interfaces.ai_suggestion_router import router as ai_suggestion_router
    from erp.modules.sys.interfaces.ai_switch_router import router as ai_switch_router
    from erp.modules.sys.interfaces.approval_router import router as approval_router
    from erp.modules.sys.interfaces.biz_center_router import router as biz_center_router
    from erp.modules.sys.interfaces.cdc_router import router as cdc_router
    from erp.modules.sys.interfaces.connector_router import router as connector_router
    from erp.modules.sys.interfaces.connector_spi_router import router as connector_spi_router
    from erp.modules.sys.interfaces.data_initializer_router import router as data_initializer_router
    from erp.modules.sys.interfaces.event_catalog_router import router as event_catalog_router
    from erp.modules.sys.interfaces.import_router import router as import_router
    from erp.modules.sys.interfaces.master_data_governance_router import router as master_data_gov_router
    from erp.modules.sys.interfaces.out_router import router as sys_out_router
    from erp.modules.sys.interfaces.param_router import router as param_router
    from erp.modules.sys.interfaces.pms_adapter_router import router as pms_adapter_router
    from erp.modules.sys.interfaces.pms_data_query_router import router as pms_data_query_router
    from erp.modules.sys.interfaces.pms_integration_router import router as pms_integration_router
    from erp.modules.sys.interfaces.pms_router import router as pms_router
    from erp.modules.sys.interfaces.router import router as sys_router
    from erp.modules.sys.interfaces.rule_router import router as rule_router
    from erp.modules.sys.interfaces.secret_store_router import router as secret_store_router
    from erp.modules.sys.interfaces.store_auth_router import router as store_auth_router
    from erp.modules.sys.interfaces.webhook_router import router as webhook_mgmt_router
    from erp.modules.tms.interfaces.logistics_connector_router import router as logistics_connector_router
    from erp.modules.tms.interfaces.out_router import router as tms_out_router
    from erp.modules.tms.interfaces.router import router as tms_router
    from erp.modules.tms.interfaces.strategy_router import router as tms_strategy_router
    from erp.modules.wms.interfaces.inventory_alert_router import router as wms_alert_router
    from erp.modules.wms.interfaces.out_router import router as wms_out_router
    from erp.modules.wms.interfaces.router import router as wms_router
    from erp.modules.wms.interfaces.transfer_router import router as wms_transfer_router

    app.include_router(admin_router, prefix=settings.admin_prefix)
    app.include_router(open_router, prefix=settings.open_prefix)
    app.include_router(webhook_router, prefix=settings.webhook_prefix)
    app.include_router(iam_router, prefix=settings.api_prefix)
    app.include_router(sys_router, prefix=settings.api_prefix)
    app.include_router(sys_out_router, prefix=settings.api_prefix)
    app.include_router(pms_router, prefix=settings.api_prefix)
    app.include_router(connector_router, prefix=settings.api_prefix)
    app.include_router(param_router, prefix=settings.api_prefix)
    app.include_router(biz_center_router, prefix=settings.api_prefix)
    app.include_router(rule_router, prefix=settings.api_prefix)
    app.include_router(ai_switch_router, prefix=settings.api_prefix)
    app.include_router(approval_router, prefix=settings.api_prefix)
    app.include_router(pms_integration_router, prefix=settings.api_prefix)
    app.include_router(event_catalog_router, prefix=settings.api_prefix)
    app.include_router(connector_spi_router, prefix=settings.api_prefix)
    app.include_router(pms_adapter_router, prefix=settings.api_prefix)
    app.include_router(webhook_mgmt_router, prefix=settings.api_prefix)
    app.include_router(store_auth_router, prefix=settings.api_prefix)
    app.include_router(secret_store_router, prefix=settings.api_prefix)
    app.include_router(import_router, prefix=settings.api_prefix)
    app.include_router(master_data_gov_router, prefix=settings.api_prefix)
    app.include_router(pms_data_query_router, prefix=settings.api_prefix)
    app.include_router(ai_suggestion_router, prefix=settings.api_prefix)
    app.include_router(data_initializer_router, prefix=settings.api_prefix)
    app.include_router(cdc_router, prefix=settings.api_prefix)
    app.include_router(pdm_router, prefix=settings.api_prefix)
    app.include_router(pdm_out_router, prefix=settings.api_prefix)
    app.include_router(som_router, prefix=settings.api_prefix)
    app.include_router(som_out_router, prefix=settings.api_prefix)
    app.include_router(oms_router, prefix=settings.api_prefix)
    app.include_router(oms_strategy_router, prefix=settings.api_prefix)
    app.include_router(oms_out_router, prefix=settings.api_prefix)
    app.include_router(scm_router, prefix=settings.api_prefix)
    app.include_router(scm_out_router, prefix=settings.api_prefix)
    app.include_router(wms_router, prefix=settings.api_prefix)
    app.include_router(wms_alert_router, prefix=settings.api_prefix)
    app.include_router(wms_transfer_router, prefix=settings.api_prefix)
    app.include_router(wms_out_router, prefix=settings.api_prefix)
    app.include_router(tms_router, prefix=settings.api_prefix)
    app.include_router(tms_strategy_router, prefix=settings.api_prefix)
    app.include_router(logistics_connector_router, prefix=settings.api_prefix)
    app.include_router(tms_out_router, prefix=settings.api_prefix)
    app.include_router(fms_router, prefix=settings.api_prefix)
    app.include_router(cost_profit_router, prefix=settings.api_prefix)
    app.include_router(billing_strategy_router, prefix=settings.api_prefix)
    app.include_router(voucher_router, prefix=settings.api_prefix)
    app.include_router(fms_out_router, prefix=settings.api_prefix)
    app.include_router(ads_router, prefix=settings.api_prefix)
    app.include_router(ads_smart_bid_router, prefix=settings.api_prefix)
    app.include_router(ads_out_router, prefix=settings.api_prefix)
    app.include_router(crm_router, prefix=settings.api_prefix)
    app.include_router(crm_lifecycle_router, prefix=settings.api_prefix)
    app.include_router(crm_out_router, prefix=settings.api_prefix)
    app.include_router(fba_router, prefix=settings.api_prefix)
    app.include_router(bi_router, prefix=settings.api_prefix)
    app.include_router(bi_metric_router, prefix=settings.api_prefix)
    app.include_router(bi_alert_router, prefix=settings.api_prefix)
    app.include_router(dashboard_router, prefix=settings.api_prefix)

    app.include_router(content_review_router, prefix=settings.api_prefix)
    app.include_router(forex_router, prefix=settings.api_prefix)
    app.include_router(payment_router, prefix=settings.api_prefix)
    app.include_router(order_strategy_router, prefix=settings.api_prefix)
    app.include_router(logistics_strategy_router, prefix=settings.api_prefix)
    app.include_router(billing_middleware_router, prefix=settings.api_prefix)
    app.include_router(cdp_router, prefix=settings.api_prefix)
    app.include_router(invoice_tax_router, prefix=settings.api_prefix)
    app.include_router(compliance_router, prefix=settings.api_prefix)
    app.include_router(selection_router, prefix=settings.api_prefix)
    app.include_router(ad_optimization_router, prefix=settings.api_prefix)
    app.include_router(cost_engine_router, prefix=settings.api_prefix)
    app.include_router(profit_engine_router, prefix=settings.api_prefix)
    app.include_router(inventory_voucher_router, prefix=settings.api_prefix)
    app.include_router(notification_center_router, prefix=settings.api_prefix)
    app.include_router(file_processor_router, prefix=settings.api_prefix)
    app.include_router(workflow_engine_router, prefix=settings.api_prefix)
    app.include_router(task_scheduler_router, prefix=settings.api_prefix)
    app.include_router(auth_center_router, prefix=settings.api_prefix)
    app.include_router(audit_center_router, prefix=settings.api_prefix)
    app.include_router(translation_center_router, prefix=settings.api_prefix)
    app.include_router(masking_center_router, prefix=settings.api_prefix)
    app.include_router(api_platform_router, prefix=settings.api_prefix)
    app.include_router(connector_platform_router, prefix=settings.api_prefix)
    app.include_router(connectors_router, prefix=settings.api_prefix)

    legacy_domain_routers = (
        ("ads", ads_out_router),
        ("crm", crm_out_router),
        ("fms", fms_out_router),
        ("oms", oms_out_router),
        ("pdm", pdm_out_router),
        ("scm", scm_out_router),
        ("som", som_out_router),
        ("sys", sys_out_router),
        ("tms", tms_out_router),
        ("wms", wms_out_router),
    )
    for domain_prefix, router in legacy_domain_routers:
        app.include_router(_clone_legacy_domain_router(router, domain_prefix))

    @app.get(f"{settings.api_prefix}/health", tags=["Health"])
    async def health():
        return Result.ok(data={"status": "UP", "version": "0.1.0"}, trace_id=trace_id_var.get(""))

    import os as _os
    _static_dir = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "static")
    if _os.path.isdir(_static_dir):
        app.mount("/static", StaticFiles(directory=_static_dir), name="static")

        @app.get("/favicon.ico", include_in_schema=False)
        async def favicon():
            return FileResponse(_os.path.join(_static_dir, "favicon.ico")) if _os.path.isfile(
                _os.path.join(_static_dir, "favicon.ico")
            ) else JSONResponse(status_code=204, content={})

        @app.get("/", include_in_schema=False)
        async def spa_index():
            return FileResponse(_os.path.join(_static_dir, "index.html"))

        @app.get("/{path:path}", include_in_schema=False)
        async def spa_fallback(path: str):
            if path.startswith(("api/", "open/", "admin/", "docs", "redoc")):
                return JSONResponse(status_code=404, content={"detail": "Not Found"})
            file_path = _os.path.join(_static_dir, path)
            if _os.path.isfile(file_path):
                return FileResponse(file_path)
            return FileResponse(_os.path.join(_static_dir, "index.html"))

    return app


app = create_app()
