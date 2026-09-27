"""mock monogoDB for unit test"""


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict] = []

    async def insert_one(self, doc: dict) -> None:
        doc["_id"] = f"fake{len(self.docs)}"
        self.docs.append(doc)

    async def insert_many(self, docs: list[dict]) -> None:
        for doc in docs:
            await self.insert_one(doc)

    async def count_documents(self, _filter: dict) -> int:
        return len(self.docs)


class FakeDB:
    def __init__(self) -> None:
        self.cols: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        return self.cols.setdefault(name, FakeCollection())
