"""mock monogoDB for unit test"""

from pymongo.errors import OperationFailure


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict] = []
        self.indexes: list[tuple] = []
        self.conflict_on_ttl = (
            False
        )

    async def insert_one(self, doc: dict) -> None:
        doc["_id"] = f"fake{len(self.docs)}"
        self.docs.append(doc)

    async def insert_many(self, docs: list[dict]) -> None:
        for doc in docs:
            await self.insert_one(doc)

    async def count_documents(self, filter: dict | None = None) -> int:
        if not filter:
            return len(self.docs)
        return sum(
            all(d.get(k) == v for k, v in filter.items() if not isinstance(v, dict))
            for d in self.docs
        )

    async def create_index(self, keys, **options) -> str:
        if self.conflict_on_ttl and "expireAfterSeconds" in options:
            raise OperationFailure("index options conflict", 85)
        self.indexes.append((keys, options))
        return "fake_index"


class FakeDB:
    def __init__(self) -> None:
        self.cols: dict[str, FakeCollection] = {}
        self.commands: list[dict] = []

    async def command(self, cmd: dict) -> dict:
        self.commands.append(cmd)
        return {"ok": 1}

    def __getitem__(self, name: str) -> FakeCollection:
        return self.cols.setdefault(name, FakeCollection())
