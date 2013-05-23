from util import SaveableMetaclass, dictify_row, stringlike


__metaclass__ = SaveableMetaclass


class Spot:
    """Controller for the icon that represents a Place.

    Spot(place, x, y, spotgraph) => a Spot representing the given
    place; at the given x and y coordinates on the screen; in the
    given graph of Spots. The Spot will be magically connected to the other
    Spots in the same way that the underlying Places are connected."""
    tables = [
        ("spot",
         {"dimension": "text not null default 'Physical'",
          "place": "text not null",
          "img": "text not null default 'orb'",
          "x": "integer not null default 50",
          "y": "integer not null default 50",
          "visible": "boolean not null default 1",
          "interactive": "boolean not null default 1"},
         ("dimension", "place"),
         {"dimension, place": ("place", "dimension, name"),
          "img": ("img", "name")},
         [])]

    def __init__(self, dimension, place, img, x, y,
                 visible, interactive, db=None):
        self.dimension = dimension
        self.place = place
        self.img = img
        self.x = x
        self.y = y
        self.visible = visible
        self.interactive = interactive
        self.grabpoint = None
        self.sprite = None
        self.oldstate = None
        self.newstate = None
        self.hovered = False
        self.tweaks = 0
        if db is not None:
            dimname = None
            placename = None
            if stringlike(self.dimension):
                dimname = self.dimension
            else:
                dimname = self.dimension.name
            if stringlike(self.place):
                placename = self.place
            else:
                placename = self.place.name
            if dimname not in db.spotdict:
                db.spotdict[dimname] = {}
            db.spotdict[dimname][placename] = self

    def __repr__(self):
        return "spot(%i,%i)->%s" % (self.x, self.y, str(self.place))

    def __eq__(self, other):
        return (
            isinstance(other, Spot) and
            self.dimension == other.dimension and
            self.name == other.name)

    def unravel(self, db):
        if stringlike(self.dimension):
            self.dimension = db.dimensiondict[self.dimension]
        if stringlike(self.place):
            self.place = db.itemdict[self.dimension.name][self.place]
        if stringlike(self.img):
            self.img = db.imgdict[self.img]
        self.rx = self.img.getwidth() / 2
        self.ry = self.img.getheight() / 2
        self.left = self.x - self.rx
        self.right = self.x + self.rx
        self.top = self.y + self.ry
        self.bot = self.y - self.ry
        self.place.spot = self

    def getleft(self):
        return self.left

    def getbot(self):
        return self.bot

    def gettop(self):
        return self.top

    def getright(self):
        return self.right

    def getcenter(self):
        return (self.x, self.y)

    def getrx(self):
        return self.rx

    def getry(self):
        return self.ry

    def gettup(self):
        return (self.img, self.getleft(), self.getbot())

    def getcoords(self):
        return (self.getleft(), self.getbot())

    def is_visible(self):
        return self.visible

    def is_interactive(self):
        return self.interactive

    def onclick(self, button, modifiers):
        pass

    def set_hovered(self):
        if not self.hovered:
            self.hovered = True
            self.tweaks += 1

    def unset_hovered(self):
        if self.hovered:
            self.hovered = False
            self.tweaks += 1

    def set_pressed(self):
        pass

    def unset_pressed(self):
        pass

    def dropped(self, x, y, button, modifiers):
        self.grabpoint = None

    def move_with_mouse(self, x, y, dx, dy, buttons, modifiers):
        if self.grabpoint is None:
            self.grabpoint = (x - self.x, y - self.y)
        (grabx, graby) = self.grabpoint
        self.x = x - grabx + dx
        self.left = self.x - self.rx
        self.right = self.x + self.rx
        self.y = y - graby + dy
        self.top = self.y + self.ry
        self.bot = self.y - self.ry

    def get_state_tup(self):
        return (
            self.img.name,
            self.x,
            self.y,
            self.visible,
            self.interactive,
            self.grabpoint,
            self.hovered,
            self.tweaks)


spot_dimension_qryfmt = (
    "SELECT {0} FROM spot WHERE dimension IN ({1})".format(
        ", ".join(Spot.colnames["spot"]), "{0}"))


def read_spots_in_boards(db, names):
    qryfmt = spot_dimension_qryfmt
    qrystr = qryfmt.format(", ".join(["?"] * len(names)))
    db.c.execute(qrystr, names)
    r = {}
    for name in names:
        r[name] = {}
    for row in db.c:
        rowdict = dictify_row(row, Spot.colnames["spot"])
        rowdict["db"] = db
        r[rowdict["dimension"]][rowdict["place"]] = Spot(**rowdict)
    return r


def unravel_spots(db, spd):
    for spot in spd.itervalues():
        spot.unravel(db)
    return spd


def unravel_spots_in_boards(db, spdd):
    for spots in spdd.itervalues():
        unravel_spots(db, spots)
    return spdd


def load_spots_in_boards(db, names):
    return unravel_spots_in_boards(db, read_spots_in_boards(db, names))
