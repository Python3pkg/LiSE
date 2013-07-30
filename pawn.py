from util import (
    SaveableMetaclass,
    TerminableImg,
    TerminableInteractivity,
    BranchTicksIter)
from logging import getLogger
from igraph import IN


logger = getLogger(__name__)


"""Widget representing things that move about from place to place."""


class Pawn(object, TerminableImg, TerminableInteractivity):
    """A token to represent something that moves about between places."""
    __metaclass__ = SaveableMetaclass
    tables = [
        ("pawn_img",
         {"dimension": "text not null default 'Physical'",
          "board": "integer not null default 0",
          "thing": "text not null",
          "branch": "integer not null default 0",
          "tick_from": "integer not null default 0",
          "tick_to": "integer default null",
          "img": "text not null default 'default_pawn'"},
         ("dimension", "board", "thing", "tick_from"),
         {"dimension, board": ("board", "dimension, i"),
          "dimension, thing": ("thing_location", "dimension, name"),
          "img": ("img", "name")},
         []),
        ("pawn_interactive",
         {"dimension": "text not null default 'Physical'",
          "board": "integer not null default 0",
          "thing": "text not null",
          "branch": "integer not null default 0",
          "tick_from": "integer not null default 0",
          "tick_to": "integer default null"},
         ("dimension", "board", "thing", "tick_from"),
         {"dimension, board": ("board", "dimension, i"),
          "dimension, thing": ("thing_location", "dimension, name")},
         [])]

    def __init__(self, board, thing):
        """Return a pawn on the board for the given dimension, representing
the given thing with the given image. It may be visible or not,
interactive or not.

With db, register in db's pawndict.

        """
        self.board = board
        self.window = self.board.window
        self.db = board.db
        self.thing = thing
        self.imagery = {}
        self.indefinite_imagery = {}
        self.interactivity = {}
        self.indefinite_interactivity = {}
        self.grabpoint = None
        self.sprite = None
        self.oldstate = None
        self.tweaks = 0
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        self.selectable = True
        self.box_edges = (None, None, None, None)

    def __str__(self):
        return str(self.thing)

    def __getattr__(self, attrn):
        if attrn == 'img':
            return self.get_img()
        elif attrn == 'visible':
            return self.img is not None
        elif attrn == 'highlit':
            return self in self.gw.selected
        elif attrn == 'interactive':
            return self.is_interactive()
        elif attrn == 'hovered':
            return self.window.hovered is self
        elif attrn == 'pressed':
            return self.window.pressed is self
        elif attrn == 'grabbed':
            return self.window.grabbed is self
        elif attrn == 'selected':
            return self in self.window.selected
        elif attrn == 'coords':
            return self.get_coords()
        elif attrn == 'x':
            c = self.coords
            if c is None:
                return 0
            else:
                return c[0]
        elif attrn == 'y':
            c = self.coords
            if c is None:
                return 0
            else:
                return c[1]
        elif attrn == 'window_left':
            return self.x + self.drag_offset_x + self.window.offset_x
        elif attrn == 'window_bot':
            return self.y + self.drag_offset_y + self.window.offset_y
        elif attrn == 'width':
            return self.img.width
        elif attrn == 'height':
            return self.img.height
        elif attrn == 'window_right':
            return self.window_left + self.width
        elif attrn == 'window_top':
            return self.window_bot + self.height
        elif attrn == 'onscreen':
            return (
                self.window_right > 0 and
                self.window_left < self.window.width and
                self.window_top > 0 and
                self.window_bot < self.window.height)
        elif attrn == 'rx':
            return self.width / 2
        elif attrn == 'ry':
            return self.height / 2
        elif attrn == 'r':
            if self.rx > self.ry:
                return self.rx
            else:
                return self.ry
        elif attrn == 'state':
                return self.get_state_tup()
        else:
            raise AttributeError(
                "Pawn instance has no such attribute: " +
                attrn)

    def __setattr__(self, attrn, val):
        if attrn == "img":
            self.set_img(val)
        elif attrn == "interactive":
            self.set_interactive(val)
        else:
            super(Pawn, self).__setattr__(attrn, val)

    def __eq__(self, other):
        """Essentially, compare the state tuples of the two pawns."""
        return self.state == other.state

    def get_state_tup(self, branch=None, tick=None):
        """Return a tuple containing everything you might need to draw me."""
        return (
            self.get_img(branch, tick),
            self.interactive,
            self.onscreen,
            self.grabpoint,
            self.hovered,
            self.get_coords(branch, tick),
            self.window_left,
            self.window_bot,
            self.tweaks)

    def move_with_mouse(self, x, y, dx, dy, buttons, modifiers):
        self.drag_offset_x += dx
        self.drag_offset_y += dy
        self.tweaks += 1

    def dropped(self, x, y, button, modifiers):
        logger.debug("Dropped the pawn %s at (%d,%d)",
                     str(self), x, y)
        self.drag_offset_x = 0
        self.drag_offset_y = 0
        spot = self.board.get_spot_at(x, y)
        if spot is not None:
            destplace = spot.place
            startplace = self.thing.location
            paths = self.thing.dimension.graph.get_shortest_paths(int(destplace), mode=IN)
            path = None
            for p in paths:
                 if p != [] and self.thing.dimension.graph.vs[p[-1]]["place"] == startplace:
                     path = [self.thing.dimension.graph.vs[i]["place"] for i in p]
            if path is None:
                return
            self.thing.add_path(path)
#            self.db.caldict[self._dimension].adjust()

    def get_coords(self, branch=None, tick=None):
        loc = self.thing.get_location(branch, tick)
        if hasattr(loc, 'dest'):
            (ox, oy) = loc.orig.spots[int(self.board)].get_coords(branch, tick)
            (dx, dy) = loc.dest.spots[int(self.board)].get_coords(branch, tick)
            ox += loc.orig.spots[int(self.board)].drag_offset_x
            dx += loc.dest.spots[int(self.board)].drag_offset_x
            oy += loc.orig.spots[int(self.board)].drag_offset_y
            dy += loc.dest.spots[int(self.board)].drag_offset_y
            prog = self.thing.get_progress(branch, tick)
            odx = dx - ox
            ody = dy - oy
            return (int(ox + odx * prog), int(oy + ody * prog))
        else:
            spot = loc.spots[int(self.board)]
            return (spot.window_x, spot.window_y)

    def get_tabdict(self):
        return {
            "pawn_img": [
                {
                    "dimension": str(self.dimension),
                    "board": int(self.board),
                    "thing": str(self.thing),
                    "branch": branch,
                    "tick_from": tick_from,
                    "tick_to": tick_to,
                    "img": str(img)}
                for (branch, tick_from, tick_to, img) in
                BranchTicksIter(self.imagery)],
            "pawn_interactive": [
                {
                    "dimension": str(self.dimension),
                    "board": int(self.board),
                    "thing": str(self.thing),
                    "branch": branch,
                    "tick_from": tick_from,
                    "tick_to": tick_to}
                for (branch, tick_from, tick_to) in
                BranchTicksIter(self.interactivity)]}
