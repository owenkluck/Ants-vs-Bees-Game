from __future__ import division

from functools import partial
from random import uniform

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.behaviors import ButtonBehavior, ToggleButtonBehavior
from kivy.properties import NumericProperty, ListProperty, ObjectProperty
from kivy.clock import Clock

from kivy.modules import inspector
from kivy.core.window import Window

import ants_vs_some_bees

__app_package__ = 'edu.unl.cse.soft161.ants_vs_some_bees'
__app__ = 'Ants vs. Some Bees'
__version__ = '0.1'
__flags__ = ['--bootstrap=sdl2', '--requirements=python2,kivy',
             '--orientation=landscape']


class ImageToggleButton(ToggleButtonBehavior, Image):
    """
    An ImageToggleButton acts like a ToggleButton, but has a source property
    and displays graphics like an Image.

    The state of an ImageToggleButton is controlled by its background color:

    * disabled_color if the button is disabled (whether selected or not)
    * unselected_color if the button is enabled but not selected
    * selected_color if the button is enabled and selected
    """

    disabled_color = ListProperty((0.5, 0.5, 0.5, 1))
    unselected_color = ListProperty((1, 1, 1, 1))
    selected_color = ListProperty((1, 1, 0, 1))


class OverlayButtonBehavior(ButtonBehavior):
    """
    An OverlayButtonBehavior provides button-like behavior to a widget with one
    key difference: the touch is not blocked from reaching widgets underneath.
    """

    def on_touch_down(self, touch):
        """
        Handle the touch-down event, but always return False to allow widgets
        underneath to process it also.
        """
        super(OverlayButtonBehavior, self).on_touch_down(touch)
        return False

    def on_touch_move(self, touch):
        """
        Handle the touch-move event, but always return False to allow widgets
        underneath to process it also.
        """
        super(OverlayButtonBehavior, self).on_touch_down(touch)
        return False

    def on_touch_up(self, touch):
        """
        Handle the touch-up event, but always return False to allow widgets
        underneath to process it also.
        """
        super(OverlayButtonBehavior, self).on_touch_down(touch)
        return False


class Sprite(OverlayButtonBehavior, Image):
    """
    A Sprite is an Image with a background color that is meant for use in
    RelativeLayouts.  Its position is controlled by two properties, world_x and
    world_y, which are scaled up by the size of one standard sprite to compute
    the Sprite's position.
    """

    world_x = NumericProperty(0)
    world_y = NumericProperty(0)
    background_color = ListProperty((0, 0, 0, 0))


class Game(BoxLayout):
    """
    A Game is a widget in which the user can play a single game of "Ants vs.
    Some Bees".  It provides a menu of ant types, a status line, and a
    battlefield display.
    """

    SPRITE_WIDTH = 93
    SPRITE_HEIGHT = 98
    REMOVER_SPRITE_FILENAME = 'assets/remover.gif'
    UNIT_SPRITE_FILENAMES = {
        ants_vs_some_bees.UnitType.BEE: 'assets/bee.gif',
        ants_vs_some_bees.UnitType.HARVESTER: 'assets/ant_harvester.gif',
        ants_vs_some_bees.UnitType.SHORT_THROWER:
            'assets/ant_short_thrower.gif',
        ants_vs_some_bees.UnitType.THROWER: 'assets/ant_thrower.gif',
        ants_vs_some_bees.UnitType.LONG_THROWER: 'assets/ant_long_thrower.gif',
        ants_vs_some_bees.UnitType.WALL: 'assets/ant_wall.gif',
    }
    LEAF_SPRITE_FILENAMES = {
        ants_vs_some_bees.UnitType.THROWER: 'assets/leaf_green.gif',
        ants_vs_some_bees.UnitType.SHORT_THROWER:
            'assets/leaf_light_green.gif',
        ants_vs_some_bees.UnitType.LONG_THROWER: 'assets/leaf_dark_green.gif',
    }
    QUEEN_SPRITE_FILENAME = 'assets/ant_queen.gif'
    TUNNEL_SPRITE_FILENAME = 'assets/tunnel.gif'
    RESPITE_COLOR = (1, 0.5, 0.5, 1)

    TURN_LENGTH = 3  # seconds per turn
    FRAME_RATE = 30  # frames per second
    FALLING_RATE = 100  # pixels per second
    THROW_DURATION = 10  # frames per throw
    MINIMUM_ARC = 0.5  # grid units
    MAXIMUM_ARC = 1.5  # grid units

    TURN_FRAMES = TURN_LENGTH * FRAME_RATE
    THROW_COEFFICIENT_2 = -1
    THROW_COEFFICIENT_1 = THROW_DURATION + 2
    THROW_COEFFICIENT_0 = -THROW_DURATION - 1
    THROW_APEX = THROW_COEFFICIENT_0 - \
        THROW_COEFFICIENT_1 ** 2 / THROW_COEFFICIENT_2 / 4

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
        Create a button in the ant menu that allows the player to purchase and
        place a copy of the given Ant archetype.  Or, if ant_archetype is None,
        create a button that allows the player to sacrifice Ants.
        """
        button = ImageToggleButton()
        button.group = 'ants-{hashcode}'.format(hashcode=hash(self))
        button.ant_archetype = ant_archetype
        button.source = \
            Game.UNIT_SPRITE_FILENAMES[ant_archetype.unit_type] \
            if ant_archetype is not None else Game.REMOVER_SPRITE_FILENAME
        button.on_press = \
            partial(self.on_press_archetype, button, ant_archetype)
        if ant_archetype is None:
            self.ids.remover = button
            self.ids.remover.state = 'down'
        self.ids.ant_menu.add_widget(button)

    def _destroy_sprite(self, sprite):
        """
        Destroy a Sprite on the battlefield.
        """
        self.ids.field.remove_widget(sprite)

    def _create_sprite(self, world_x, world_y, sprite_filename):
        """
        Create a Sprite at the given coordinates on the battlefield displaying
        the given image file.
        """
        sprite = Sprite()
        sprite.world_x = world_x
        sprite.world_y = world_y
        sprite.source = sprite_filename
        self.ids.field.add_widget(sprite)
        return sprite

    def _create_insect_sprite(self, insect, place):
        """
        Create a Sprite for an Insect to be displayed at the given Place.
        The parameter place usually matches insect.place, but does not have to;
        for instance, an Ant immediately killed might have its sprite at a
        Place even though the Ant itself is dead and not at any Place.
        """
        assert insect not in self.insect_sprites, \
            'Cannot create multiple sprites for {insect}'.format(insect=insect)
        filename = Game.UNIT_SPRITE_FILENAMES[insect.unit_type]
        sprite = self._create_sprite(place.world_x, place.world_y, filename)
        self.insect_sprites[insect] = sprite

    def _create_place_sprite(self, place):
        """
        Create a Sprite for a Place.  The Sprite is automatically positioned.
        """
        if isinstance(place, ants_vs_some_bees.ColonyPlace):
            sprite = self._create_sprite(place.world_x, place.world_y,
                                         Game.TUNNEL_SPRITE_FILENAME)
            if isinstance(place, ants_vs_some_bees.Respite):
                sprite.background_color = Game.RESPITE_COLOR
            sprite.on_press = partial(self.on_press_place, place)
            return sprite
        elif place is self.game_state.queen_place:
            return self._create_sprite(place.world_x, place.world_y,
                                       Game.QUEEN_SPRITE_FILENAME)
        else:
            return None

    def _refresh_food(self):
        """
        Ensure that the amount of food displayed as available matches the
        amount of food actually available.
        """
        self.food = self.game_state.food

    def _build(self):
        """
        Create the subwidgets and start the game.  The subwidgets include the
        buttons for purchasing and sacrificing Ants, the Place Sprites, the Bee
        Sprites, and the initial Ant Sprites.
        """
        for archetype in self.game_state.ant_archetypes:
            self._create_ant_button(archetype)
        self._create_ant_button(None)

        max_x = max(place.world_x for place in self.game_state.places) + 1
        max_y = max(place.world_y for place in self.game_state.places) + 1
        self.ids.field.size = (Game.SPRITE_WIDTH * (max_x + 1),
                               Game.SPRITE_HEIGHT * (max_y + 1))
        self.ids.field_scroll.scroll_x = 0.5
        self.ids.field_scroll.scroll_y = 0.5

        for place in self.game_state.places:
            self._create_place_sprite(place)

        # Insects should be created after places so that they can't go "under"
        # a tunnel.

        for ant in self.game_state.get_ants():
            self._create_insect_sprite(ant, ant.place)

        for bee in self.game_state.get_bees():
            self._create_insect_sprite(bee, bee.place)

        self._refresh_food()

        self.animator = Clock.schedule_interval(lambda delta: self.animate(),
                                                1 / Game.FRAME_RATE)

    def _animate_insect(self, insect, sprite):
        """
        Reposition the given Sprite to match the state of the given Insect
        according to the Game's current frame count.
        """
        place = insect.place
        if place is not None:
            weight = 1 / self.frames_until_next_turn
            counterweight = 1 - weight
            sprite.world_x = \
                weight * place.world_x + counterweight * sprite.world_x
            sprite.world_y = \
                weight * place.world_y + counterweight * sprite.world_y
        else:
            sprite.y -= Game.FALLING_RATE / Game.FRAME_RATE

    def _animate_leaf(self, leaf):
        """
        Reposition the given leaf Sprite to match the leaf's trajectory
        according to the Game's current frame count.
        """
        if self.frames_until_next_turn <= Game.THROW_DURATION:
            weight = (self.frames_until_next_turn - 1) / Game.THROW_DURATION
            counterweight = 1 - weight
            arc_delta = \
                (Game.THROW_COEFFICIENT_2 * self.frames_until_next_turn ** 2 +
                 Game.THROW_COEFFICIENT_1 * self.frames_until_next_turn +
                 Game.THROW_COEFFICIENT_0) / Game.THROW_APEX
            leaf.world_x = \
                weight * leaf.source_x + counterweight * leaf.target_x
            leaf.world_y = \
                weight * leaf.source_y + counterweight * leaf.target_y + \
                leaf.arc * arc_delta

    def _refresh_leaves(self):
        """
        Destroy all existing leaf Sprites and replace them with a new set, one
        leaf for each Ant that attacked a Bee.  Also, configure those leaves'
        trajectories to represent those attacks.
        """
        for leaf in self.leaf_sprites:
            self._destroy_sprite(leaf)
        self.leaf_sprites = []
        for ant in self.game_state.get_ants():
            target = ant.get_target_place()
            if target is not None:
                sprite_filename = self.LEAF_SPRITE_FILENAMES[ant.unit_type]
                sprite = self._create_sprite(ant.place.world_x,
                                             ant.place.world_y,
                                             sprite_filename)
                sprite.source_x = sprite.world_x
                sprite.source_y = sprite.world_y
                sprite.target_x = target.world_x
                sprite.target_y = target.world_y
                sprite.arc = uniform(Game.MINIMUM_ARC, Game.MAXIMUM_ARC)
                self.leaf_sprites.append(sprite)

    def animate(self):
        """
        Advance to the next frame of animation.  If enough frames have passed
        for the game to reach the next turn, advance the game and refresh the
        widget accordingly.
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
        Respond to presses on an ant menu button by ensuring that one ant menu
        button is always selected and that the selection property holds the
        corresponding archetype.
        """
        if button.state == 'down' and ant_archetype is not None:
            self.selection = ant_archetype
        else:
            self.selection = None
            self.ids.remover.state = 'down'

    def on_press_place(self, place):
        """
        Respond to presses on a Place Sprite by placing an Ant (provided the
        GameState allows the placement) based on the current selection.
        """
        if self.selection is not None:
            ant = self.game_state.place_ant(self.selection, place)
            if ant is not None:
                self._create_insect_sprite(ant, place)
                self._refresh_food()
        else:
            self.game_state.sacrifice_ant(place.get_defender())


class TowerApp(App):
    def build(self):
        """
        Add an inspector to the app to make debugging easier.
        """
        inspector.create_inspector(Window, self)

    def begin_game(self):
        """
        Create a new GameState and an associated Game widget and scroll to that
        widget.
        """
        self.root.transition.direction = 'down'
        self.root.current = 'go'
        game = Game(ants_vs_some_bees.make_standard_game())
        game.bind(outcome=self.on_outcome)
        self.root.ids.go.add_widget(game)

    def end_game(self):
        """
        Destroy the Game widget and scroll back to the main screen.
        """
        go_screen = self.root.ids.go
        go_screen.remove_widget(go_screen.children[0])
        self.root.transition.direction = 'up'
        self.root.current = 'ready'

    def on_outcome(self, _, outcome):
        """
        Listen for changes to the game's outcome and call end_game if the game
        has ended.
        """
        if outcome is not ants_vs_some_bees.GameOutcome.UNRESOLVED:
            self.end_game()


if __name__ == "__main__":
    app = TowerApp()
    app.run()
