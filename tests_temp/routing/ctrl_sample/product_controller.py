from adapters.web.routing import delete, get


class ProductController:
    prefix = "/products"
    tags = ["products"]

    @get("/{product_id}")
    async def get_product(self, product_id: int) -> dict:
        return {"id": product_id}

    @delete("/{product_id}", status_code=204)
    async def delete_product(self, product_id: int) -> None:
        return None
