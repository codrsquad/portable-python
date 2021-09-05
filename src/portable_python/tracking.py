import runez


class Trackable:

    tracked_category = None

    def __eq__(self, other):
        return str(self) == str(other)

    def __hash__(self):
        return hash(str(self))

    def __iter__(self):
        yield self


class TrackedCollection:

    def __init__(self, name):
        self.name = name
        self.items = []

    def __repr__(self):
        return "%s %s" % (len(self.items), self.name)

    def __bool__(self):
        return bool(self.items)

    def add(self, item):
        if item not in self.items:
            self.items.append(item)

    def represented(self, verbose=False):
        if self.items:
            for item in self.items:
                yield item.represented(verbose=verbose)


class Tracker(TrackedCollection):

    def __init__(self, enum, name=None):
        self.kind = enum.__name__.replace("Type", "").lower()
        super().__init__(name or self.kind)
        self.enum = enum
        self.category = {}
        self.users = {}
        for x in enum:
            c = TrackedCollection("%s %s" % (x.name, self.kind))
            self.category[x] = c

    def add(self, item):
        if item not in self.items:
            self.items.append(item)

        for trackable in item:
            if trackable.tracked_category:
                c = self.category[trackable.tracked_category]
                c.add(trackable)
                if trackable is not item:
                    u = self.users.get(trackable)
                    if u is None:
                        u = set()
                        self.users[trackable] = u

                    u.add(item)

    def represented(self, verbose=False):
        report = []
        if self.items:
            for item in self.items:
                report.append(item.represented(verbose))

        report = runez.joined(report, delimiter="\n")
        if verbose or report:
            report = "\n-- %s\n%s" % (runez.colored(self, "bold"), report)

        return report
