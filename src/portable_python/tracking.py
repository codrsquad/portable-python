import abc
import enum
from collections.abc import Iterator

import runez


class LibType(enum.Enum):
    """Categorization for dynamic libs, value being the color we want to show them as"""

    base = ""
    lib_static = "static"
    libpython_so = "dynamic"
    missing = "red"
    other = "brown"
    system = "blue"


class Trackable(abc.ABC):
    """A file (dynamic lib, .so, ...) that can be tracked by a `Tracker`"""

    relative_path: str
    tracked_category: LibType  # Set by leaf trackables only, the ones yielded by `__iter__()`

    def __eq__(self, other: object) -> bool:
        return str(self) == str(other)

    def __hash__(self) -> int:
        return hash(str(self))

    def __iter__(self) -> Iterator["Trackable"]:
        yield self

    @abc.abstractmethod
    def represented(self, verbose: bool = False) -> str:
        """Textual representation, for reports"""


class TrackedCollection:
    def __init__(self, name: str):
        self.name = name
        self.items: list[Trackable] = []

    def __repr__(self):
        return "%s %s" % (len(self.items), self.name)

    def __bool__(self):
        return bool(self.items)

    def add(self, item: Trackable):
        if item not in self.items:
            self.items.append(item)

    def represented(self, verbose: bool = False) -> Iterator[str]:
        for item in self.items:
            yield item.represented(verbose=verbose)


class Tracker(TrackedCollection):
    def __init__(self, name: str = "lib"):
        super().__init__(name)
        self.category = {x: TrackedCollection(f"{x.name} lib") for x in LibType}
        self.users: dict[Trackable, set[Trackable]] = {}

    def add(self, item: Trackable):
        super().add(item)
        for trackable in item:
            self.category[trackable.tracked_category].add(trackable)
            if trackable is not item:
                self.users.setdefault(trackable, set()).add(item)

    def report(self, verbose: bool = False) -> str:
        report = runez.joined(self.represented(verbose), delimiter="\n")
        if verbose or report:
            report = "\n-- %s\n%s" % (runez.colored(self, "bold"), report)

        return report
