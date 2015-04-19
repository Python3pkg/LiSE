from .pallet import Pallet, PalletBox
from .kivygarden.texturestack import ImageStack
from kivy.clock import Clock
from kivy.lang import Builder
from kivy.logger import Logger
from kivy.properties import (
    ListProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty
)
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.boxlayout import BoxLayout


class SpriteSelector(BoxLayout):
    prefix = StringProperty()
    pallets = ListProperty()
    imgpaths = ListProperty([])
    default_imgpaths = ListProperty()
    preview = ObjectProperty()

    def on_prefix(self, *args):
        if 'textbox' not in self.ids:
            Clock.schedule_once(self.on_prefix, 0)
            return
        self.ids.textbox.text = self.prefix

    def on_imgpaths(self, *args):
        if not self.preview:
            Logger.debug(
                "SpriteSelector: no preview"
            )
            Clock.schedule_once(self.on_imgpaths, 0)
            return
        if hasattr(self, '_imgstack'):
            self.preview.remove_widget(self._imgstack)
        self._imgstack = ImageStack(
            paths=self.imgpaths,
            x=self.preview.center_x - 16,
            y=self.preview.center_y - 16
        )
        self.preview.add_widget(self._imgstack)

    def on_pallets(self, *args):
        for pallet in self.pallets:
            pallet.bind(selection=self._upd_imgpaths)

    def _upd_imgpaths(self, *args):
        imgpaths = []
        for pallet in self.pallets:
            if pallet.selection:
                for selected in pallet.selection:
                    imgpaths.append(
                        'atlas://{}/{}'.format(
                            pallet.filename,
                            selected.name
                        )
                    )
        self.imgpaths = imgpaths if imgpaths else self.default_imgpaths


class SpriteBuilder(ScrollView):
    prefix = StringProperty()
    imgpaths = ListProperty()
    default_imgpaths = ListProperty()
    layout = ObjectProperty()
    data = ListProperty()
    labels = ListProperty()
    pallets = ListProperty()

    def __init__(self, **kwargs):
        self._trigger_update = Clock.create_trigger(self.update)
        self._trigger_reheight = Clock.create_trigger(self.reheight)
        super().__init__(**kwargs)
        self.bind(
            data=self._trigger_update
        )

    def update(self, *args):
        if self.data is None:
            return
        if not self.canvas:
            Clock.schedule_once(self.update, 0)
            return
        if not hasattr(self, '_palbox'):
            self._palbox = PalletBox(
                orientation='vertical',
                size_hint_y=None
            )
            self.add_widget(self._palbox)
        else:
            self._palbox.clear_widgets()
        self.labels = []
        self.pallets = []
        for (text, filename) in self.data:
            label = Label(
                text=text,
                size_hint=(None, None),
                halign='center'
            )
            label.texture_update()
            label.height = label.texture.height
            label.width = self._palbox.width
            self._palbox.bind(width=label.setter('width'))
            pallet = Pallet(
                filename=filename,
                size_hint=(None, None)
            )
            pallet.width = self._palbox.width
            self._palbox.bind(width=pallet.setter('width'))
            pallet.height = pallet.minimum_height
            pallet.bind(
                minimum_height=pallet.setter('height'),
                height=self._trigger_reheight
            )
            self.labels.append(label)
            self.pallets.append(pallet)
        n = len(self.labels)
        assert(n == len(self.pallets))
        for i in range(0, n):
            self._palbox.add_widget(self.labels[i])
            self._palbox.add_widget(self.pallets[i])

    def reheight(self, *args):
        self._palbox.height = sum(
            wid.height for wid in self.labels + self.pallets
        )


class SpriteDialog(BoxLayout):
    cb = ObjectProperty()
    prefix = StringProperty()
    imgpaths = ListProperty()
    default_imgpaths = ListProperty()
    layout = ObjectProperty()
    data = ListProperty()
    pallet_box_height = NumericProperty()

    def pressed(self):
        self.prefix = self.ids.selector.prefix
        self.imgpaths = self.ids.selector.imgpaths
        self.cb()


class PawnConfigDialog(SpriteDialog):
    def on_layout(self, *args):
        self.cb = self.layout.toggle_pawn_config
        self.data = [
            ('Body', 'base.atlas'),
            ('Basic clothes', 'body.atlas'),
            ('Armwear', 'arm.atlas'),
            ('Legwear', 'leg.atlas'),
            ('Right hand', 'hand1.atlas'),
            ('Left hand', 'hand2.atlas'),
            ('Boots', 'boot.atlas'),
            ('Hair', 'hair.atlas'),
            ('Beard', 'beard.atlas'),
            ('Headwear', 'head.atlas')
        ]


class SpotConfigDialog(SpriteDialog):
    def on_layout(self, *args):
        self.cb = self.layout.toggle_spot_config
        self.data = [('Dungeon', 'dungeon.atlas')]


Builder.load_string("""
<SpriteDialog>:
    orientation: 'vertical'
    SpriteBuilder:
        id: builder
        prefix: root.prefix
        default_imgpaths: root.default_imgpaths
        layout: root.layout
        imgpaths: root.imgpaths
        data: root.data
    SpriteSelector:
        id: selector
        textbox: textbox
        size_hint_y: 0.1
        prefix: root.prefix
        default_imgpaths: root.default_imgpaths
        imgpaths: root.imgpaths
        pallets: builder.pallets
        preview: preview
        TextInput:
            id: textbox
            multiline: False
            write_tab: False
            hint_text: 'Enter name prefix'
        Widget:
            id: preview
        Button:
            text: 'OK'
            on_press: root.pressed()
<PawnConfigDialog>:
    default_imgpaths: ['atlas://base.atlas/unseen']
<SpotConfigDialog>:
    default_imgpaths: ['orb.png']
""")