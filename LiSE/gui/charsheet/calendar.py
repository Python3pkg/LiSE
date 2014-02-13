# This file is part of LiSE, a framework for life simulation games.
# Copyright (c) 2013 Zachary Spector,  zacharyspector@gmail.com
from kivy.clock import Clock
from kivy.properties import (
    AliasProperty,
    DictProperty,
    BoundedNumericProperty,
    ListProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
    ReferenceListProperty,
    OptionProperty
)
from kivy.uix.relativelayout import RelativeLayout
from kivy.uix.stacklayout import StackLayout
from kivy.uix.stencilview import StencilView
from kivy.uix.layout import Layout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.logger import Logger
from kivy.graphics import Color, Line, Triangle

from LiSE.util import CALENDAR_TYPES
from LiSE.gui.kivybits import LiSEWidgetMetaclass


class Cell(Label):
    __metaclass__ = LiSEWidgetMetaclass
    kv = """
<Cell>:
    valign: 'top'
    text_size: self.size
    color: solarized['base00']
    text: self.closet.get_text(self.stringname)\
    if self.closet and self.stringname else ''
    canvas.before:
        Color:
            rgba: solarized['base2']
        Rectangle:
            pos: root.pos
            size: root.size
    """
    closet = ObjectProperty()
    stringname = StringProperty()


class Timeline(Widget):
    """A wedge and a line to show where the current moment is on the
    calendar."""
    r = BoundedNumericProperty(1., min=0., max=1.)
    g = BoundedNumericProperty(0., min=0., max=1.)
    b = BoundedNumericProperty(0., min=0., max=1.)
    a = BoundedNumericProperty(1., min=0., max=1.)
    color = ReferenceListProperty(r, g, b, a)
    calendar = ObjectProperty()

    def __init__(self, **kwargs):
        super(Timeline, self).__init__(**kwargs)
        self.colorinst = Color(*self.color)
        self.canvas.add(self.colorinst)
        self.lineinst = Line(
            points=[self.x, self.y, self.x+self.calendar.col_width, self.y])
        self.canvas.add(self.lineinst)
        self.triinst = Triangle(points=[
            self.x, self.y+8, self.x+16, self.y, self.x, self.y-8])
        self.canvas.add(self.triinst)

    def on_color(self, *args):
        if not hasattr(self, 'colorinst'):
            return
        self.colorinst.rgba = self.color

    def on_pos(self, *args):
        if not hasattr(self, 'lineinst'):
            return
        self.lineinst.points = [
            self.x, self.y, self.x+self.calendar.col_width, self.y]
        if not hasattr(self, 'triinst'):
            return
        self.triinst.points = [
            self.x, self.y+8, self.x+16, self.y, self.x, self.y-8]


class Column(StackLayout):
    view = ObjectProperty()
    adapter = ObjectProperty()
    calendar = ObjectProperty()
    branch = NumericProperty()
    data = ListProperty()
    firsttick = NumericProperty()
    lasttick = NumericProperty()
    closet = AliasProperty(
        lambda self: self.calendar.charsheet.character.closet,
        lambda self, v: None,
        bind=('calendar',))
    skel = ObjectProperty()
    boneatt = StringProperty()
    tick_height = NumericProperty()
    mintick = NumericProperty()
    maxtick = NumericProperty()

    def __init__(self, **kwargs):
        self._trigger_redata = Clock.create_trigger(self.redata)
        self._trigger_x = Clock.create_trigger(self.re_x)
        super(Column, self).__init__(**kwargs)
        self.skel.unregister_set_listener(self._trigger_redata)
        self.skel.unregister_del_listener(self._trigger_redata)
        self.skel.register_set_listener(self._trigger_redata)
        self.skel.register_del_listener(self._trigger_redata)
        self.redata()

    def re_x(self, *args):
        self.x = (self.calendar.col_width +
                  self.calendar.spacing_x) * self.branch

    def args_converter(self, idx, bone):
        try:
            bone2 = self.data[idx+1]
            return {
                'closet': self.closet,
                'size_hint_y': None,
                'height': (bone2.tick - bone.tick) * self.tick_height,
                'top': self.top - (bone.tick * self.tick_height),
                'stringname': getattr(bone, self.boneatt)}
        except IndexError:
            return {
                'closet': self.closet,
                'size_hint_y': None,
                'height': (max(self.calendar.view.hi_tick,
                               self.height / self.tick_height) -
                           bone.tick) * self.tick_height,
                'top': self.top - (bone.tick * self.tick_height),
                'stringname': getattr(bone, self.boneatt)}

    def gen_cells(self):
        i = 0
        firsttick = -1
        lasttick = -1
        for bone in self.data:
            if self.mintick <= bone.tick <= self.maxtick:
                if firsttick == -1:
                    self.firsttick = bone.tick
                lasttick = bone.tick
                celargs = self.args_converter(i, bone)
                yield Cell(**celargs)
            i += 1
        self.firsttick = firsttick
        self.lasttick = lasttick

    def redata(self, *args):
        self.data = list(self.skel.iterbones())
        self.clear_widgets()
        for cell in self.gen_cells():
            self.add_widget(cell)


class Calendar(Layout):
    """A gridlike layout of cells representing events throughout every
    branch of the timestream.

    It will fill itself in based on what it finds in the Skeleton under
    the given keys. Only the events that can be seen at the moment, and a
    few just out of view, will be instantiated.

    It may be scrolled by dragging. It will snap to some particular branch
    and tick when dropped.

    A timeline will be drawn on top of it, but that is not instantiated
    here. Look in CalendarView below.

    """
    __metaclass__ = LiSEWidgetMetaclass
    kv = """
<Calendar>:
    font_name: 'DroidSans'
    font_size: 20
    branches_wide: 2
    spacing: (5, 5)
    offscreen: (2, 2)
    tick_height: 2
    col_width: 100
"""
    branches_wide = NumericProperty()
    """The number of columns in the calendar that are visible at
    once. Each represents a branch of the timestream."""
    boneatt = StringProperty()
    """What attribute of its bone each cell should display for its text"""
    cal_type = OptionProperty('thing_cal', options=CALENDAR_TYPES)
    """Integer to indicate where in the skeleton to look up the bones for
    the cells"""
    col_width = BoundedNumericProperty(100, min=50)
    """How wide a column of the calendar should be"""
    col_height = NumericProperty()
    key = StringProperty()
    """The *most specific* element of the partial key identifying the
    records of the calendar's referent, not including the branch and
    tick.

    """
    stat = StringProperty()
    """Name of the stat the calendar displays. Might be one of the special
    stats like location or origin."""
    font_name = StringProperty()
    """Font to be used for labels in cells"""
    font_size = NumericProperty()
    """Size of font to be used for labels in cells"""
    spacing_x = NumericProperty()
    """Space between columns"""
    spacing_y = NumericProperty()
    """Space between cells"""
    spacing = ReferenceListProperty(
        spacing_x, spacing_y)
    """[spacing_x, spacing_y]"""
    tick_height = NumericProperty()
    """How much screen a single tick should take up"""
    ticks_offscreen = NumericProperty()
    """How far off the screen a cell should be allowed before it's
    deleted--measured in ticks"""
    branches_offscreen = NumericProperty()
    """How many columns should be kept in memory, despite being offscreen"""
    offscreen = ReferenceListProperty(
        branches_offscreen, ticks_offscreen)
    """[branches_offscreen, ticks_offscreen]"""
    branch = BoundedNumericProperty(0, min=0)
    """The leftmost branch I show"""
    tick = BoundedNumericProperty(0, min=0)
    """The topmost tick I show"""
    time = ReferenceListProperty(branch, tick)
    """[branch, tick]"""
    referent = ObjectProperty()
    """The sim-object I am about"""
    skel = ObjectProperty()
    """That portion of the grand skeleton I am concerned with"""
    view = ObjectProperty()
    cal_type = AliasProperty(
        lambda self: self.view.mybone.type,
        lambda self, v: None,
        bind=('view',))
    charsheet = AliasProperty(
        lambda self: self.view.charsheet,
        lambda self, v: None,
        bind=('view',))
    """Character sheet I'm in"""
    character = AliasProperty(
        lambda self: self.view.charsheet.character
        if self.charsheet else None,
        lambda self, v: None,
        bind=('view',))
    """Conveniently reach the character"""
    closet = AliasProperty(
        lambda self: self.view.charsheet.character.closet
        if self.charsheet else None,
        lambda self, v: None,
        bind=('view',))
    """Conveniently reach the closet"""
    branches_cols = DictProperty()
    """How many ticks fit in me at once"""
    minbranch = NumericProperty()
    maxbranch = NumericProperty()
    mintick = NumericProperty()
    maxtick = NumericProperty()

    def __init__(self, **kwargs):
        self._trigger_redata = Clock.create_trigger(self.redata)
        super(Calendar, self).__init__(**kwargs)

    def finalize(self, *args):
        """Collect my referent--the object I am about--and my skel--the
        portion of the great Skeleton that pertains to my
        referent. Arrange to be notified whenever I need to lay myself
        out again.

        """
        if not (self.character and self.key and self.stat):
            Clock.schedule_once(self.finalize, 0)
            return

        character = self.character
        closet = character.closet
        skeleton = closet.skeleton

        if self.cal_type == 'thing_cal':
            self.referent = self.character.get_thing(self.key)
            if self.stat == "location":
                self.skel = skeleton["thing_loc"][
                    unicode(self.character)][self.key]
                self.boneatt = "location"
            else:
                self.skel = skeleton["thing_stat"][
                    unicode(self.character)][self.key][self.stat]
                self.boneatt = "value"
        elif self.cal_type == 'place_cal':
            self.referent = self.character.get_place(self.key)
            self.skel = skeleton["place_stat"][
                unicode(self.character)][self.key][self.stat]
            self.boneatt = "value"
        elif self.cal_type == 'portal_cal':
            if self.stat in ("origin", "destination"):
                self.skel = skeleton["portal_loc"][
                    unicode(self.character)][self.key]
                self.boneatt = self.stat
            else:
                self.skel = skeleton["portal_stat"][
                    unicode(self.character)][self.key][self.stat]
                self.boneatt = "value"
        elif self.cal_type == 'char_cal':
            self.skel = skeleton["character_stat"][
                unicode(self.character)][self.key]
            self.boneatt = "value"
        else:
            Clock.schedule_once(self.finalize, 0)
            return
        self.redata()

    def redata(self, *args):
        def col_skel_updater(branch):
            def upd_col_skel(*args):
                self.branches_cols[branch].skel = self.skel[branch]
            return upd_col_skel

        if self.mintick == self.maxtick:
            Clock.schedule_once(self.redata)
            return

        for branch in xrange(0, self.closet.timestream.hi_branch+1):
            if branch not in self.skel:
                if branch in self.branches_cols:
                    self.remove_widget(self.branches_cols[branch])
                continue
            elif (
                    branch not in self.branches_cols or
                    not isinstance(self.branches_cols[branch],
                                   Column)):
                col = Column(
                    calendar=self,
                    branch=branch,
                    size_hint=(None, 1),
                    width=self.col_width,
                    x=(self.col_width + self.spacing_x) * branch,
                    top=self.top,
                    skel=self.skel[branch],
                    boneatt=self.boneatt,
                    tick_height=self.tick_height,
                    mintick=self.mintick,
                    maxtick=self.maxtick)
                self.branches_cols[branch] = col
                self.bind(x=col._trigger_x,
                          top=col.setter('top'),
                          boneatt=col.setter('boneatt'),
                          tick_height=col.setter('tick_height'),
                          mintick=col.setter('mintick'),
                          maxtick=col.setter('maxtick'))
                self.skel[branch].register_listener(
                    col_skel_updater(branch))
            try:
                if (
                        self.skel[branch].key_or_key_before(self.mintick)
                        != self.branches_cols[branch].firsttick):
                    self.branches_cols[branch]._trigger_redata()
            except ValueError:
                pass
            try:
                if (
                        self.skel[branch].key_or_key_after(self.maxtick)
                        != self.branches_cols[branch].lasttick):
                    self.branches_cols[branch]._trigger_redata()
            except ValueError:
                pass
            self.add_widget(self.branches_cols[branch])

    def do_layout(self, *args):
        for child in self.children:
            x = self.x + (self.col_width + self.spacing_x) * child.branch
            if x != child.x:
                child.x = x
            if child.width != self.col_width:
                child.width = self.col_width
            if child.top != self.top:
                child.top = self.top
        super(Calendar, self).do_layout(*args)


class CalendarView(StencilView):
    """A StencilView displaying a Calendar and a Timeline."""
    i = NumericProperty()
    """Index in the character sheet"""
    calendar = ObjectProperty()
    """I exist to hold this"""
    timeline = ObjectProperty()
    """Must put this in the view not the calendar, because it's supposed
    to stay on top, always

    """
    charsheet = ObjectProperty()
    """Character sheet I'm in"""
    mybone = ObjectProperty()
    closet = AliasProperty(
        lambda self: self.charsheet.character.closet,
        lambda self, v: None,
        bind=('charsheet',))
    branch = NumericProperty()
    hi_branch = NumericProperty()
    tick = NumericProperty()
    hi_tick = NumericProperty()
    time = ReferenceListProperty(branch, tick)
    hi_time = ReferenceListProperty(hi_branch, hi_tick)
    _touch = ObjectProperty(None, allownone=True)
    """For when I've been grabbed and should handle scrolling"""

    def __init__(self, **kwargs):
        """Construct the calendar and the timeline atop it."""
        self._trigger_clayout_pos = Clock.create_trigger(
            self.upd_clayout_pos)
        self._trigger_clayout_size = Clock.create_trigger(
            self.upd_clayout_size)
        self._trigger_time = Clock.create_trigger(
            self.upd_time)
        super(CalendarView, self).__init__(**kwargs)
        self.calendar = Calendar(
            view=self,
            key=kwargs['key'],
            stat=kwargs['stat'])
        self.clayout = RelativeLayout(top=self.top, x=self.x)
        self.upd_clayout_size(self.closet.timestream,
                              *self.closet.timestream.hi_time)
        self.add_widget(self.clayout)
        self.clayout.add_widget(self.calendar)
        self.timeline = Timeline(
            color=kwargs['tl_color'] if 'tl_color' in kwargs
            else [1, 0, 0, 1],
            calendar=self.calendar)
        self.clayout.add_widget(self.timeline)
        self.calendar.finalize()

        def set_time(b, t):
            self.time = (b, t)

        def set_hi_time(b, t):
            self.hi_time = (b, t)
        self.closet.register_time_listener(set_time)
        self.closet.register_hi_time_listener(set_hi_time)
        self.bind(pos=self._trigger_clayout_pos)
        self.bind(time=self._trigger_time)
        self.closet.timestream.hi_time_listeners.append(
            self._trigger_clayout_size)
        self.time = self.closet.time

    def upd_time(self, *args):
        (branch, tick) = self.time
        x = (self.calendar.col_width + self.calendar.spacing_x) * branch
        y = self.clayout.height - self.calendar.tick_height * tick
        if self.timeline.pos != (x, y):
            self.timeline.pos = (x, y)
        minbranch = int(max(
            0, self.calendar.branch -
            self.calendar.branches_offscreen))
        if minbranch != self.calendar.minbranch:
            self.calendar.minbranch = minbranch
        maxbranch = int(max(
            self.hi_branch, self.calendar.branch +
            self.calendar.branches_wide +
            self.calendar.branches_offscreen))
        if maxbranch != self.calendar.maxbranch:
            self.calendar.maxbranch = maxbranch
        mintick = int(max(
            0, self.calendar.tick - self.calendar.ticks_offscreen))
        if mintick != self.calendar.mintick:
            self.calendar.mintick = mintick
        maxtick = int(max(
            self.hi_tick, self.calendar.tick +
            self.hi_tick + self.calendar.ticks_offscreen))
        if maxtick != self.calendar.maxtick:
            self.calendar.maxtick = maxtick

    def upd_clayout_size(self, *args):
        hi_branch = self.closet.timestream.hi_branch
        hi_tick = self.closet.timestream.hi_tick
        w = (self.calendar.col_width + self.calendar.spacing_x) * hi_branch
        h = self.calendar.tick_height * hi_tick
        size = (w, max(100, h))
        if self.clayout.size != size:
            self.clayout.size = size

    def upd_clayout_pos(self, *args):
        if self._touch:
            return
        if self.clayout.x != self.x:
            self.clayout.x = self.x
        if self.clayout.top != self.top:
            self.clayout.top = self.top

    def on_touch_down(self, touch):
        """Detect grab. If grabbed, put 'calendar' and 'charsheet' into
        touch.ud

        """
        if self.collide_point(touch.x, touch.y):
            self._touch = touch
            touch.grab(self)
            touch.ud['calendar'] = self.calendar
            touch.ud['charsheet'] = self.charsheet
            # clayout's current position
            touch.ud['clox'] = self.clayout.x
            touch.ud['cloy'] = self.clayout.y
            return True

    def on_touch_move(self, touch):
        """If grabbed, move the calendar based on how far the touch has gone
        from where it started

        """
        if self._touch is touch:
            x = touch.ud['clox'] + touch.x - touch.ox
            y = touch.ud['cloy'] + touch.y - touch.oy
            self.clayout.pos = (x, y)
            self.calendar.tick = max(0, int((
                self.clayout.top - self.top) / self.calendar.tick_height))
            self.calendar.branch = max(0, int((
                self.x - self.clayout.x) / (
                self.calendar.col_width + self.calendar.spacing_x)))
            return True
        else:
            self._touch = None
            touch.ungrab(self)

    def on_touch_up(self, touch):
        """If the calendar's been dragged, it should adjust itself so it's at
        whatever time it should be

        """
        _touch = self._touch
        self._touch = None
        if _touch is not touch:
            return
        x = self.clayout.x
        top = self.clayout.top
        x -= x % (self.calendar.col_width + self.calendar.spacing_x)
        x = max(self.x, x)
        top -= top % self.calendar.tick_height
        top = max(self.top, top)
        self.clayout.x = x
        self.clayout.top = top
        return True
