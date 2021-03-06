from functools import partial
from random import uniform

from kivy.app import App
from kivy.properties import NumericProperty, StringProperty, ListProperty, ObjectProperty
from kivy.uix.label import Label
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.behaviors import ButtonBehavior, ToggleButtonBehavior
from kivy.clock import Clock

from kivy.modules import inspector
from kivy.core.window import Window

import ants_vs_some_bees


class Text(Label):
    pass


class Paragraph(Text):
    pass


class CaptionedSprite(BoxLayout):
    source = StringProperty('')
    text = StringProperty('')


class ImageToggleButton(ToggleButtonBehavior, Image):
    """
    An ImageToggleButton acts like a ToggleButton, but has a source property and displays graphics like an Image.

    The state of an ImageToggleButton is expressed by its background color:
    * disabled_color if the button is disabled (whether selected or not),
    * unselected_color if the button is enabled but not selected, or
    * selected_color if the button is enabled and selected.
    """
    # noinspection PyArgumentList
    disabled_color = ListProperty((0.5, 0.5, 0.5, 1))
    # noinspection PyArgumentList
    unselected_color = ListProperty((1, 1, 1, 1))
    # noinspection PyArgumentList
    selected_color = ListProperty((1, 1, 0, 1))


class OverlayButtonBehavior(ButtonBehavior):
    """
    An OverlayButtonBehavior provides button-like behavior to a widget with one key difference: the touch is not blocked
    from reaching widgets underneath.
    """
    def on_touch_down(self, touch):
        """
        Handle the touch-down event, but always return False to allow widgets underneath to process it also.
        """
        super().on_touch_down(touch)
        return False

    def on_touch_move(self, touch):
        """
        Handle the touch-move event, but always return False to allow widgets underneath to process it also.
        """
        super().on_touch_down(touch)
        return False

    def on_touch_up(self, touch):
        """
        Handle the touch-up event, but always return False to allow widgets underneath to process it also.
        """
        super().on_touch_down(touch)
        return False


class Sprite(OverlayButtonBehavior, Image):
    """
    A Sprite is an Image that is meant for use in RelativeLayouts.  Its position is controlled by two properties,
    world_x and world_y, which are scaled up by the size of one standard sprite to compute the Sprite's position.
    """
    world_x = NumericProperty(0)
    world_y = NumericProperty(0)
    scale = NumericProperty(1)

    def __init__(self, world_x, world_y, z_index, sprite_filename, **kwargs):
        super().__init__(**kwargs)
        self.world_x = world_x
        self.world_y = world_y
        self.z_index = z_index
        self.source = sprite_filename
        self.source_x = None  # Used by _refresh_leaves
        self.source_y = None  # Used by _refresh_leaves
        self.target_x = None  # Used by _refresh_leaves
        self.target_y = None  # Used by _refresh_leaves
        self.arc = None  # Used by _refresh_leaves


class Game(BoxLayout):
    """
    A Game is a widget in which the user can play a single game of "Ants vs. Some Bees".  It provides a menu of ant
    types, a status line, and a battlefield display.
    """

    SPRITE_WIDTH = 93
    SPRITE_HEIGHT = 98
    GROUND_Z_INDEX = 0
    ANT_Z_INDEX = 1
    BEE_Z_INDEX = 2
    LEAF_Z_INDEX = 3

    REMOVER_SPRITE_FILENAME = 'assets/remover.png'
    UNIT_SPRITE_FILENAMES = {
        ants_vs_some_bees.UnitType.BEE: 'assets/bee.png',
        ants_vs_some_bees.UnitType.HARVESTER: 'assets/ant_harvester.png',
        ants_vs_some_bees.UnitType.THROWER: 'assets/ant_medium.png',
        ants_vs_some_bees.UnitType.SUPER_HARVESTER: 'assets/ant_fire.png',
        ants_vs_some_bees.UnitType.MEGA_THROWER: 'assets/ant_large.png',
        ants_vs_some_bees.UnitType.SUPER_THROWER: 'assets/ant_ninja.png',
    }
    LEAF_SPRITE_FILENAMES = {
        ants_vs_some_bees.UnitType.THROWER: 'assets/leaf_green.png',
        ants_vs_some_bees.UnitType.SUPER_THROWER: 'assets/leaf_green.png',
        ants_vs_some_bees.UnitType.MEGA_THROWER: 'assets/leaf_dark_green.png'
    }
    QUEEN_SPRITE_FILENAME = 'assets/ant_queen.png'
    PLACE_SPRITE_FILENAME = 'assets/place.png'

    TURN_LENGTH = 3  # seconds per turn
    FRAME_RATE = 30  # frames per second
    FALLING_RATE = 1  # z units per second
    THROW_DURATION = 10  # frames per throw
    MINIMUM_ARC = 0.5  # grid units
    MAXIMUM_ARC = 1.5  # grid units

    TURN_FRAMES = TURN_LENGTH * FRAME_RATE
    THROW_COEFFICIENT_2 = -1  # coefficient of t?? in the animation parabola
    THROW_COEFFICIENT_1 = THROW_DURATION + 2  # coefficient of t?? in the animation parabola
    THROW_COEFFICIENT_0 = -THROW_DURATION - 1  # coefficient of t??? in the animation parabola
    THROW_APEX = THROW_COEFFICIENT_0 - THROW_COEFFICIENT_1 ** 2 / THROW_COEFFICIENT_2 / 4

    selection = ObjectProperty(None, allownone=True)
    time = NumericProperty(0)
    food = NumericProperty(0)
    outcome = ObjectProperty(ants_vs_some_bees.GameOutcome.UNRESOLVED)

    def __init__(self, game_state):
        """
        Create a Game to represent and manipulate the given game state.
        """
        super(Game, self).__init__()
        self.frames_until_next_turn = Game.TURN_FRAMES
        self.insect_sprites = {}
        self.leaf_sprites = []
        self.game_state = game_state
        self._build()

    def _create_ant_button(self, ant_archetype):
        """
        Create a button in the ant menu that allows the player to purchase and place a copy of the given Ant archetype.
        Or, if ant_archetype is None, create a button that allows the player to sacrifice Ants.
        """
        button = ImageToggleButton()
        button.group = 'ants-{hashcode}'.format(hashcode=hash(self))
        button.source = Game.UNIT_SPRITE_FILENAMES[ant_archetype.unit_type] if ant_archetype is not None else\
            Game.REMOVER_SPRITE_FILENAME
        button.on_press = partial(self.on_press_archetype, button, ant_archetype)
        if ant_archetype is None:
            self.ids.remover = button
            self.ids.remover.state = 'down'
        self.ids.ant_menu.add_widget(button)

    def _destroy_sprite(self, sprite):
        """
        Destroy a Sprite on the battlefield.
        """
        self.ids.field.remove_widget(sprite)

    def _create_sprite(self, world_x, world_y, sprite_filename, z_index):
        """
        Create a Sprite at the given coordinates on the battlefield displaying the given image file.
        """
        sprite = Sprite(world_x, world_y, z_index, sprite_filename)
        field = self.ids.field
        field.add_widget(sprite, sum(child.z_index > z_index for child in field.children))
        return sprite

    def _create_insect_sprite(self, insect, place, z_index):
        """
        Create a Sprite for an Insect to be displayed at the given Place.  The parameter place usually matches
        insect.place, but does not have to; for instance, an Ant immediately killed might have its sprite at a Place
        even though the Ant itself is dead and not at any Place.
        """
        assert insect not in self.insect_sprites, f'Cannot create multiple sprites for {insect}'
        filename = Game.UNIT_SPRITE_FILENAMES[insect.unit_type]
        sprite = self._create_sprite(place.world_x, place.world_y, filename, z_index)
        self.insect_sprites[insect] = sprite

    def _create_place_sprite(self, place):
        """
        Create a Sprite for a Place.  The Sprite is automatically positioned.
        """
        if isinstance(place, ants_vs_some_bees.ColonyPlace):
            sprite = self._create_sprite(place.world_x, place.world_y, Game.PLACE_SPRITE_FILENAME, Game.GROUND_Z_INDEX)
            sprite.on_press = partial(self.on_press_place, place)
            return sprite
        if place is self.game_state.queen_place:
            return self._create_sprite(place.world_x, place.world_y, Game.QUEEN_SPRITE_FILENAME, Game.ANT_Z_INDEX)
        return None

    def _refresh_food(self):
        """
        Ensure that the amount of food displayed as available matches the amount of food actually available.
        """
        self.food = self.game_state.food

    def _build(self):
        """
        Create the subwidgets and start the game.  The subwidgets include the buttons for purchasing and sacrificing
        Ants, the Place Sprites, the Bee Sprites, and the initial Ant Sprites.
        """
        for archetype in self.game_state.ant_archetypes:
            self._create_ant_button(archetype)
        # noinspection PyTypeChecker
        self._create_ant_button(None)

        max_x = max(place.world_x for place in self.game_state.places) + 1
        max_y = max(place.world_y for place in self.game_state.places) + 1
        self.ids.field.size = (Game.SPRITE_WIDTH * (max_x + 1), Game.SPRITE_HEIGHT * (max_y + 1))
        self.ids.field_scroll.scroll_x = 0.5
        self.ids.field_scroll.scroll_y = 0.5

        for place in self.game_state.places:
            self._create_place_sprite(place)
        for ant in self.game_state.ants:
            self._create_insect_sprite(ant, ant.place, Game.ANT_Z_INDEX)
        for bee in self.game_state.bees:
            self._create_insect_sprite(bee, bee.place, Game.BEE_Z_INDEX)

        self._refresh_food()

        self.animator = Clock.schedule_interval(lambda delta: self.animate(), 1 / Game.FRAME_RATE)

    def _animate_insect(self, insect, sprite):
        """
        Reposition the given Sprite to match the state of the given Insect according to the Game's current frame count.
        """
        place = insect.place
        if place is not None:
            weight = 1 / self.frames_until_next_turn
            counterweight = 1 - weight
            sprite.world_x = weight * place.world_x + counterweight * sprite.world_x
            sprite.world_y = weight * place.world_y + counterweight * sprite.world_y
        elif sprite.scale > 0:
            sprite.scale = max(1 / (1 / (sprite.scale + 0.5) + Game.FALLING_RATE / Game.FRAME_RATE) - 0.5, 0)

    def _animate_leaf(self, leaf):
        """
        Reposition the given leaf Sprite to match the leaf's trajectory according to the Game's current frame count.
        """
        if self.frames_until_next_turn <= Game.THROW_DURATION:
            weight = (self.frames_until_next_turn - 1) / Game.THROW_DURATION
            counterweight = 1 - weight
            arc_delta = \
                (Game.THROW_COEFFICIENT_2 * self.frames_until_next_turn ** 2 +
                 Game.THROW_COEFFICIENT_1 * self.frames_until_next_turn +
                 Game.THROW_COEFFICIENT_0) / Game.THROW_APEX
            leaf.world_x = weight * leaf.source_x + counterweight * leaf.target_x
            leaf.world_y = weight * leaf.source_y + counterweight * leaf.target_y + leaf.arc * arc_delta

    def _refresh_leaves(self):
        """
        Destroy all existing leaf Sprites and replace them with a new set, one leaf for each Ant that attacked a Bee.
        Also, configure those leaves' trajectories to represent those attacks.
        """
        for leaf in self.leaf_sprites:
            self._destroy_sprite(leaf)
        self.leaf_sprites = []
        for ant in self.game_state.ants:
            target = ant.target_place
            if target is not None:
                sprite_filename = self.LEAF_SPRITE_FILENAMES[ant.unit_type]
                sprite = self._create_sprite(ant.place.world_x, ant.place.world_y, sprite_filename, Game.LEAF_Z_INDEX)
                sprite.source_x = sprite.world_x
                sprite.source_y = sprite.world_y
                sprite.target_x = target.world_x
                sprite.target_y = target.world_y
                sprite.arc = uniform(Game.MINIMUM_ARC, Game.MAXIMUM_ARC)
                self.leaf_sprites.append(sprite)

    def animate(self):
        """
        Advance to the next frame of animation.  If enough frames have passed for the game to reach the next turn,
        advance the game and refresh the widget accordingly.
        """
        for insect, sprite in self.insect_sprites.items():
            self._animate_insect(insect, sprite)
        for leaf in self.leaf_sprites:
            self._animate_leaf(leaf)
        self.frames_until_next_turn -= 1
        if self.frames_until_next_turn <= 0:
            self.outcome = self.game_state.take_turn()
            if self.outcome is not ants_vs_some_bees.GameOutcome.UNRESOLVED:
                self.animator.loop = False
            self.time += 1
            self.frames_until_next_turn = Game.TURN_FRAMES
            self._refresh_leaves()
            self._refresh_food()

    def on_press_archetype(self, button, ant_archetype):
        """
        Respond to presses on an ant menu button by ensuring that one ant menu button is always selected and that the
        selection property holds the corresponding archetype.
        """
        if button.state == 'down' and ant_archetype is not None:
            self.selection = ant_archetype
        else:
            self.selection = None
            self.ids.remover.state = 'down'

    def on_press_place(self, place):
        """
        Respond to presses on a Place Sprite by placing an Ant (provided the GameState allows the placement) based on
        the current selection.
        """
        if self.selection is not None:
            ant = self.game_state.place_ant(self.selection, place)
            if ant is not None:
                self._create_insect_sprite(ant, place, Game.ANT_Z_INDEX)
                self._refresh_food()
        else:
            self.game_state.sacrifice_ant(place.defender)


class TowerApp(App):
    def build(self):
        """
        Add an inspector to the app to make debugging easier.
        """
        inspector.create_inspector(Window, self)

    def begin_game(self):
        """
        Create a new GameState and an associated Game widget and scroll to that widget.
        """
        self.root.transition.direction = 'down'
        self.root.current = 'game'
        standard_game = ants_vs_some_bees.make_standard_game()
        standard_game.diagnostics = True
        game = Game(standard_game)
        game.bind(outcome=self.on_outcome)
        self.root.ids.game_screen.add_widget(game)

    def end_game(self):
        """
        Destroy the Game widget and scroll back to the main screen.
        """
        game_screen = self.root.ids.game_screen
        game_screen.remove_widget(game_screen.children[0])
        self.root.transition.direction = 'up'
        self.root.current = 'ready'

    def on_outcome(self, _, outcome):
        """
        Listen for changes to the game's outcome and call end_game if the game has ended.
        """
        if outcome is not ants_vs_some_bees.GameOutcome.UNRESOLVED:
            self.end_game()


if __name__ == '__main__':
    app = TowerApp()
    app.run()
