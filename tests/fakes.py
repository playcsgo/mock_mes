"""mock monogoDB for unit test"""

from pymongo.errors import OperationFailure


class FakeCursor:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def sort(self, key: str, direction: int = 1) -> "FakeCursor":
        self.rows = sorted(self.rows, key=lambda d: d[key], reverse=direction < 0)
        return self

    def limit(self, n: int) -> "FakeCursor":
        self.rows = self.rows[:n]
        return self

    async def to_list(self) -> list[dict]:
        return [dict(d) for d in self.rows]

    def __aiter__(self):
        async def gen():
            for d in self.rows:
                yield dict(d)

        return gen()


class FakeCollection:
    def __init__(self) -> None:
        self.docs: list[dict] = []
        self.indexes: list[tuple] = []
        self.conflict_on_ttl = False

    async def insert_one(self, doc: dict) -> None:
        doc["_id"] = f"fake{len(self.docs)}"
        self.docs.append(doc)

    async def insert_many(self, docs: list[dict]) -> None:
        for doc in docs:
            await self.insert_one(doc)

    def _match(self, doc: dict, filter: dict) -> bool:
        return all(doc.get(k) == v for k, v in filter.items())

    async def update_one(self, filter: dict, update: dict, upsert: bool = False):
        for doc in self.docs:
            if self._match(doc, filter):
                doc.update(update.get("$set", {}))
                return
        if upsert:
            doc = {**filter, **update.get("$set", {}), **update.get("$setOnInsert", {})}
            await self.insert_one(doc)

    async def find_one(self, filter: dict) -> dict | None:
        return next((dict(d) for d in self.docs if self._match(d, filter)), None)

    async def find_one_and_update(self, filter: dict, update: dict, **options):
        # the real one is atomic; a list scan with no await in between is too
        for doc in self.docs:
            if self._match(doc, filter):
                doc.update(update.get("$set", {}))
                return dict(doc)
        return None

    async def delete_one(self, filter: dict) -> None:
        for i, doc in enumerate(self.docs):
            if self._match(doc, filter):
                del self.docs[i]
                return

    def find(self, filter: dict | None = None, projection: dict | None = None):
        return FakeCursor([d for d in self.docs if self._match(d, filter or {})])

    async def distinct(self, key: str) -> list:
        return sorted({d[key] for d in self.docs if key in d})

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
