# This file is part of LiSE, a framework for life simulation games.
# Copyright (c) 2013-2014 Zachary Spector,  zacharyspector@gmail.com
from kivy.properties import (
    DictProperty,
    ObjectProperty,
    NumericProperty,
    ListProperty
)
from kivy.clock import Clock
from kivy.uix.relativelayout import RelativeLayout
from .spot import Spot
from .arrow import Arrow
from .pawn import Pawn


class Board(RelativeLayout):
    """A graphical view onto a facade, resembling a game board."""
    layout = ObjectProperty()
    character = ObjectProperty()
    spot = DictProperty({})
    pawn = DictProperty({})
    arrow = DictProperty({})
    arrow_bg = ListProperty()
    arrow_fg = ListProperty()
    arrow_width = NumericProperty()
    arrowhead_size = NumericProperty()
    arrowlayout = ObjectProperty()
    spotlayout = ObjectProperty()
    pawnlayout = ObjectProperty()
    app = ObjectProperty()
    engine = ObjectProperty()
    spots_unposd = NumericProperty(0)

    def __init__(self, **kwargs):
        """Make a trigger for ``_redata`` and run it"""
        self._trigger_update = Clock.create_trigger(self._update)
        super().__init__(**kwargs)

    def make_pawn(self, thing):
        """Make a :class:`Pawn` to represent a :class:`Thing`"""
        if thing["name"] in self.pawn:
            raise KeyError("Already have a Pawn for this Thing")
        r = Pawn(
            board=self,
            thing=thing
        )
        self.pawn[thing["name"]] = r
        return r

    def make_spot(self, place):
        """Make a :class:`Spot` to represent a :class:`Place`"""
        if place["name"] in self.spot:
            raise KeyError("Already have a Spot for this Place")
        r = Spot(
            board=self,
            place=place
        )
        self.spot[place["name"]] = r
        return r

    def make_arrow(self, portal):
        """Make an :class:`Arrow` to represent a :class:`Portal`"""
        if (
                portal["origin"] not in self.spot or
                portal["destination"] not in self.spot
        ):
            raise ValueError(
                "An :class:`Arrow` should only be made after "
                "the :class:`Spot`s it connects"
            )
        if (
                portal["origin"] in self.arrow and
                portal["destination"] in self.arrow[portal["origin"]]
        ):
            raise KeyError("Already have an Arrow for this Portal")
        r = Arrow(
            board=self,
            engine=self.engine,
            portal=portal
        )
        if portal["origin"] not in self.arrow:
            self.arrow[portal["origin"]] = {}
        self.arrow[portal["origin"]][portal["destination"]] = r
        return r

    def on_character(self, *args):
        """Arrange to save my scroll state in my character, and to get updated
        whenever my character is

        """
        if self.character is None or self.engine is None:
            Clock.schedule_once(self.on_character, 0)
            return

        def updscrollx(*args):
            self.character.stat['_scroll_x'] = self.parent.scroll_x
        trigger_updscrollx = Clock.create_trigger(updscrollx)

        def updscrolly(*args):
            self.character.stat['_scroll_y'] = self.parent.scroll_y
        trigger_updscrolly = Clock.create_trigger(updscrolly)

        for prop in '_scroll_x', '_scroll_y':
            if (
                    prop not in self.character.stat or
                    self.character.stat[prop] is None
            ):
                self.character.stat[prop] = 0.0

        self.parent.scroll_x = self.character.stat['_scroll_x']
        self.parent.scroll_y = self.character.stat['_scroll_y']
        self.parent.bind(scroll_x=trigger_updscrollx)
        self.parent.bind(scroll_y=trigger_updscrolly)

        @self.engine.on_time
        def ontime(*args):
            self._trigger_update()

        self._trigger_update()

    def _rmpawn(self, name):
        """Remove the :class:`Pawn` by the given name"""
        if name not in self.pawn:
            raise KeyError("No Pawn")
        pwn = self.pawn[name]
        pwn.parent.remove_widget(pwn)
        del self.pawn[name]

    def _rmspot(self, name):
        """Remove the :class:`Spot` by the given name"""
        if name not in self.spot:
            raise KeyError("No Spot")
        self.spotlayout.remove_widget(self.pawn[name])
        del self.spot[name]

    def _rmarrow(self, orig, dest):
        """Remove the :class:`Arrow` that goes from ``orig`` to ``dest``"""
        if (
                orig not in self.arrow or
                dest not in self.arrow[orig]
        ):
            raise KeyError("No Arrow")
        self.spotlayout.remove_widget(self.arrow[orig][dest])
        del self.arrow[orig][dest]

    def nx_layout(self, graph):
        from networkx import spectral_layout
        return spectral_layout(graph)

    def _update(self, *args):
        """Refresh myself from the database"""
        # remove widgets that don't represent anything anymore
        for pawn_name in list(self.pawn.keys()):
            if pawn_name not in self.character.thing:
                self._rmpawn(pawn_name)
        for spot_name in list(self.spot.keys()):
            if spot_name not in self.character.place:
                self._rmspot(spot_name)
        for arrow_origin in list(self.arrow.keys()):
            for arrow_destination in list(self.arrow[arrow_origin].keys()):
                if (
                        arrow_origin not in self.character.portal or
                        arrow_destination not in
                        self.character.portal[arrow_origin]
                ):
                    self._rmarrow(arrow_origin, arrow_destination)
        # add widgets to represent new stuff
        for place_name in self.character.place:
            if place_name not in self.spot:
                self.spotlayout.add_widget(
                    self.make_spot(self.character.place[place_name])
                )
        if self.spots_unposd == len(self.spot):
            # No spots have positions;
            # do a layout.
            spots_only = self.character.facade()
            for thing in list(spots_only.thing.keys()):
                del spots_only.thing[thing]
            l = self.nx_layout(spots_only)
            for (spot, (x, y)) in l.items():
                self.spot[spot].pos = (
                    int(x * self.width),
                    int(y * self.height)
                )
        for arrow_orig in self.character.portal:
            for arrow_dest in self.character.portal[arrow_orig]:
                if (
                        arrow_orig not in self.arrow or
                        arrow_dest not in self.arrow[arrow_orig]
                ):
                    self.arrowlayout.add_widget(
                        self.make_arrow(
                            self.character.portal[arrow_orig][arrow_dest]
                        )
                    )
        for thing_name in self.character.thing:
            if thing_name not in self.pawn:
                pwn = self.make_pawn(self.character.thing[thing_name])
                try:
                    whereat = self.arrow[
                        pwn.thing['location']
                    ][
                        pwn.thing['next_location']
                    ]
                except KeyError:
                    whereat = self.spot[pwn.thing['location']]
                whereat.add_widget(pwn)
                self.pawn[thing_name] = pwn
        for spot in self.spot.values():
            spot._trigger_update()
        for pawn in self.pawn.values():
            pawn._trigger_update()

    def __repr__(self):
        """Look like a :class:`Character` wrapped in ``Board(...)```"""
        return "Board({})".format(repr(self.character))

    def on_touch_down(self, touch):
        """Check pawns, ``spotlayout``, and ``arrowlayout`` in turn,
        stopping and returning the first true result I get.

        Assign the result to my layout's ``grabbed`` attribute.

        """
        for pawn in self.pawn.values():
            if pawn.dispatch('on_touch_down', touch):
                return True
            if pawn.collide_point(*touch.pos):
                pawn._touch = touch
                self.layout.grabbed = pawn
                return True
        for child in self.spotlayout.children:
            if child.dispatch('on_touch_down', touch):
                self.layout.grabbed = child
                return True
        for child in self.arrowlayout.children:
            if child.dispatch('on_touch_down', touch):
                self.layout.grabbed = child
                return True
