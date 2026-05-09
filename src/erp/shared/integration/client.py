"""
跨域服务化调用模块

提供 DomainServiceClient 作为跨域调用的统一入口，
各域通过 Protocol 接口定义服务契约，保持领域独立性。
"""
from erp.shared.integration.client import DomainServiceClient

__all__ = ["DomainServiceClient"]
