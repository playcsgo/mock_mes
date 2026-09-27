"""mock monogoDB for unit test"""


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict] = []
        self.indexes: list[tuple] = []

    async def insert_one(self, doc: dict) -> None:
        doc["_id"] = f"fake{len(self.docs)}"
        self.docs.append(doc)

    async def insert_many(self, docs: list[dict]) -> None:
        for doc in docs:
            await self.insert_one(doc)

    async def count_documents(self, filter: dict | None = None) -> int:
        # Equality conditions only ({"station": "ST-01"}); enough for the tests
        if not filter:
            return len(self.docs)
        return sum(
            all(d.get(k) == v for k, v in filter.items() if not isinstance(v, dict))
            for d in self.docs
        )

    async def create_index(self, keys, **options) -> str:
        self.indexes.append((keys, options))
        return "fake_index"


class FakeDB:
    def __init__(self) -> None:
        self.cols: dict[str, FakeCollection] = {}

    def __getitem__(self, name: str) -> FakeCollection:
        return self.cols.setdefault(name, FakeCollection())
