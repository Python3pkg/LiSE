from kivy.app import App
from kivy.clock import Clock
from kivy.properties import (
    BoundedNumericProperty,
    ObjectProperty,
    StringProperty,
    DictProperty,
    AliasProperty
)
from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.textinput import TextInput

from kivy.factory import Factory

from .charsheet import CharSheet
from .texturestack import ImageStack

import LiSE
import ELiDE

_ = lambda x: x

Factory.register('CharSheet', cls=CharSheet)


class TouchlessWidget(Widget):
    """Widget made not to interact with any touch"""
    def on_touch_down(self, *args):
        """Nothing"""
        pass

    def on_touch_move(self, *args):
        """Nothing"""
        pass

    def on_touch_up(self, *args):
        """Nothing"""
        pass


class DummySpot(Widget):
    """This is at the end of the arrow that appears when you're drawing a
    new portal. It's invisible, serving only to mark the pixel the
    arrow ends at for the moment.

    """
    def collide_point(self, *args):
        """This should be wherever you point, and therefore, always
        collides."""
        return True

    def on_touch_move(self, touch):
        """Center to touch"""
        self.center = touch.pos


class DummyPawn(ImageStack):
    """Looks like a Pawn, but doesn't have a Thing associated.

    This is meant to be used when the user is presently engaged with
    deciding where a Thing should be. The Thing in question
    doesn't exist yet, but you know what it should look like.

    """
    thing_name = StringProperty()
    board = ObjectProperty()
    callback = ObjectProperty()

    def on_touch_down(self, touch):
        """Grab the touch if it hits me."""
        if self.collide_point(touch.x, touch.y):
            touch.grab(self)
            touch.ud['pawn'] = self
            return True

    def on_touch_move(self, touch):
        """If I've been grabbed, move to the touch."""
        if 'pawn' in touch.ud and touch.ud['pawn'] is self:
            self.center = touch.pos

    def on_touch_up(self, touch):
        """Create a real Pawn on top of the Spot I am likewise on top of,
        along with a Thing for it to represent.

        """
        if 'pawn' not in touch.ud:
            return
            pass  # TODO


class ELiDELayout(FloatLayout):
    """A very tiny master layout that contains one board and some menus
    and charsheets.

    This contains three elements: a board, a menu, and a character
    sheet. This class has some support methods for handling
    interactions with the menu and the character sheet, but if neither
    of those happen, the board handles touches on its own.

    """
    app = ObjectProperty()
    """The App instance that is running and thus holds the globals I need."""
    _touch = ObjectProperty(None, allownone=True)
    popover = ObjectProperty()
    """The modal view to use for the various menus that aren't visible by
    default."""
    portaling = BoundedNumericProperty(0, min=0, max=2)
    """Count how far along I am in the process of connecting two Places by
    creating a Portal between them."""
    playspeed = BoundedNumericProperty(0, min=0)
    grabbed = ObjectProperty(None, allownone=True)
    engine = AliasProperty(
        lambda self: self.app.engine,
        lambda self, v: None,
        bind=('app',)
    )

    def on_touch_down(self, touch):
        """Delegate first to the charsheet, then to the board, then to the
        boardview.

        """
        self.grabbed = self.ids.charsheet.on_touch_down(touch)
        if self.grabbed is None:
            self.grabbed = self.ids.board.on_touch_down(touch)
        if self.grabbed is None:
            return self.ids.boardview.on_touch_down(touch)

    def on_touch_move(self, touch):
        """If something's been grabbed, transform the touch to the boardview's
        space and then delegate there.

        """
        # I think I should handle charsheet special
        if self.grabbed is None:
            return self.ids.boardview.on_touch_move(touch)
        else:
            touch.push()
            touch.apply_transform_2d(self.ids.boardview.to_local)
            r = self.grabbed.on_touch_move(touch)
            touch.pop()
            return r


Factory.register('ELiDELayout', cls=ELiDELayout)


class MenuIntInput(TextInput):
    """Field for inputting an integer"""
    engine = ObjectProperty()
    stringname = StringProperty()
    attrname = StringProperty()

    def __init__(self, **kwargs):
        """Create trigger for upd_time, then delegate to super"""
        self._trigger_upd_time = Clock.create_trigger(self.upd_time)
        super(MenuIntInput, self).__init__(**kwargs)

    def insert_text(self, s, from_undo=False):
        """Natural numbers only."""
        return super(self, MenuIntInput).insert_text(
            ''.join(c for c in s if c in '0123456789'),
            from_undo
        )

    def on_engine(self, *args):
        """Arrange that I'll be updated every time the game-time changes"""
        if self.engine:
            self.engine.on_time(
                self._trigger_upd_time
            )

    def on_text_validate(self, *args):
        """Set the engine's attribute to my value cast as an int"""
        setattr(self.engine, self.attrname, int(self.text))

    def upd_time(self, *args):
        """Change my hint text to the engine's attribute, then blank out my
        regular text

        """
        self.hint_text = str(getattr(self.engine, self.attrname))
        self.text = ''


Factory.register('MenuIntInput', cls=MenuIntInput)


class ELiDEApp(App):
    """LiSE, run as a standalone application, and not a library.

    As it's a Kivy app, this implements the things required of the App
    class. I also keep \"globals\" here.

    """
    engine = ObjectProperty()
    cli_args = DictProperty({})

    def build_config(self, config):
        """Set config defaults"""
        for sec in 'LiSE', 'ELiDE':
            config.adddefaultsection(sec)
        config.setdefaults(
            'LiSE',
            {
                'world': 'LiSEworld.db',
                'code': 'LiSEcode.db',
                'language': 'en'
            }
        )
        config.setdefaults(
            'ELiDE',
            {
                'wallpaper': ELiDE.__path__[0] + "/assets/wallpape.jpg",
                'boardchar': 'physical',
                'sheetchar': 'player'
            }
        )
        for sec in self.cli_args:
            for (k, v) in self.cli_args[sec].items():
                config[sec][k] = v
        config.write()

    def build(self):
        """Make sure I can use the database, create the tables as needed, and
        return the root widget.

        """
        config = self.config
        self.engine = LiSE.Engine(
            config['LiSE']['world'],
            config['LiSE']['code']
        )
        for char in config['ELiDE']['boardchar'], config['ELiDE']['sheetchar']:
            if char not in self.engine.character:
                self.engine.add_character(char)
        l = ELiDELayout(app=self)
        from kivy.core.window import Window
        from kivy.modules import inspector
        inspector.create_inspector(Window, l)
        return l

    def on_pause(self):
        """Sync the database with the current state of the game."""
        self.engine.commit()

    def stop(self, *largs):
        """Sync the database, wrap up the game, and halt."""
        self.engine.close()
        super().stop(*largs)
