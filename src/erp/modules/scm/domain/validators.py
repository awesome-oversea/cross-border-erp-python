from __future__ import annotations


class SupplierRatingCalculator:
    WEIGHTS = {"quality": 0.4, "delivery": 0.25, "price": 0.2, "service": 0.15}

    def calculate(self, quality_score: float, delivery_score: float, price_score: float, service_score: float) -> dict:
        overall = (
            quality_score * self.WEIGHTS["quality"]
            + delivery_score * self.WEIGHTS["delivery"]
            + price_score * self.WEIGHTS["price"]
            + service_score * self.WEIGHTS["service"]
        )

        if overall >= 90:
            level = "strategic"
        elif overall >= 75:
            level = "preferred"
        elif overall >= 60:
            level = "normal"
        else:
            level = "observation"

        return {
            "overall_score": round(overall, 2),
            "level": level,
            "breakdown": {
                "quality": round(quality_score, 2),
                "delivery": round(delivery_score, 2),
                "price": round(price_score, 2),
                "service": round(service_score, 2),
            },
        }
