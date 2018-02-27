from __future__ import division

from copy import deepcopy
from random import choice, uniform
from enum import Enum


class Place(object):
    """
    A Place holds bees and is linked to other Places.
    """

    def __init__(self, world_x, world_y):
        """
        Create a Place at the given x and y coordinates.
        """
        self.world_x = world_x
        self.world_y = world_y
        self.sources = []
        self.destinations = []
        self.bees = []

    def connect_to(self, place):
        """
        Create a connection between this Place and the one given; Bees will
        travel from this Place to the other one.
        """
        self.destinations.append(place)
        place.sources.append(self)

    def get_defender(self):
        """
        Return the ant defending this place, if any. 
        """
        return None

    def add_insect(self, insect):
        """
        Add an Insect to this Place.

        A plain Place can only hold bees. There can be any number of Bees in a
        Place.
        """
        assert isinstance(insect, Bee), \
            'The place {place} cannot hold {added} of the type {kind}' \
            .format(place=self, added=insect, kind=type(insect).__name__)
        assert insect not in self.bees, \
            'The bee {bee} cannot be added to {place} twice' \
            .format(place=self, bee=insect)
        self.bees.append(insect)
        insect.place = self

    def remove_insect(self, insect):
        """
        Remove an Insect from this Place.
        """
        assert insect in self.bees, \
            '{bee} is not at {place} to be removed' \
            .format(bee=insect, place=self)
        self.bees.remove(insect)
        insect.place = None

    def __repr__(self):
        return '{name}({x}, {y})' \
            .format(name=type(self).__name__, x=self.world_x, y=self.world_y)


class ColonyPlace(Place):
    """
    A ColonyPlace, unlike a regular Place, can hold an Ant and be the target of
    an Ant's attack.
    """

    def __init__(self, world_x, world_y):
        """
        Create a ColonyPlace at the given coordinates.
        """
        super(ColonyPlace, self).__init__(world_x, world_y)
        self.ant = None

    def get_defender(self):
        """
        Return the ant defending this place, if any.
        """
        return self.ant

    def add_insect(self, insect):
        """
        Add an Insect to this Place.

        There can be at most one Ant in a ColonyPlace. If add_insect tries to
        add more Ants than is allowed, an AssertionError is raised.

        There can be any number of Bees in a Place.
        """
        if isinstance(insect, Ant):
            assert self.ant is None, \
                'The place {place} cannot hold both {current} and {added}' \
                .format(place=self, current=self.ant, added=insect)
            self.ant = insect
            insect.place = self
        else:
            super(ColonyPlace, self).add_insect(insect)

    def remove_insect(self, insect):
        """
        Remove an Insect from this Place.
        """
        if isinstance(insect, Ant):
            assert insect is self.ant, \
                'The ant {ant} is not at {place} to be removed' \
                .format(ant=insect, place=self)
            self.ant = None
            insect.place = None
        else:
            super(ColonyPlace, self).remove_insect(insect)


class Respite(ColonyPlace):
    """
    A respite is a kind of Place that boosts Bees' health when they enter it.
    """

    def __init__(self, world_x, world_y, health_boost=1):
        """
        Create a Respite that boosts Bees' health by the given amount.
        """
        super(Respite, self).__init__(world_x, world_y)
        self.health_boost = health_boost


class UnitType(Enum):
    """
    A UnitType represents how an Insect looks to the player.  It is possible
    for otherwise identical Insects to have different UnitTypes, and it is also
    possible for fundamentally different Insects to have the same UnitType.

    Any changes to this Enum should be accompanied by corresponding changes to
    the frontend in main.py and tower.kv.
    """
    BEE = 'BEE'
    HARVESTER = 'HARVESTER'
    SHORT_THROWER = 'SHORT_THROWER'
    THROWER = 'THROWER'
    LONG_THROWER = 'LONG_THROWER'
    WALL = 'WALL'


class Insect(object):
    """
    An Insect, the base class of Ant and Bee, has health and damage and also a
    Place.
    """

    def __init__(self, unit_type, health=1, damage=0):
        """
        Create an Insect with the given type, health, and damage..
        """
        self.unit_type = unit_type
        self.health = health
        self.damage = damage
        self.place = None  # set by Place.add_insect and Place.remove_insect

    def reduce_health(self, amount):
        """
        Reduce health by amount, and remove the insect from its place if it has
        no health remaining.
        """
        self.health -= amount
        if self.health <= 0 and self.place is not None:
            self.place.remove_insect(self)

    def act(self, game_state):
        """
        Perform the action that this Insect takes for this turn.
        """
        pass

    def __repr__(self):
        return '{kind}({unit_type}, {health}, {place})' \
            .format(kind=type(self).__name__, unit_type=self.unit_type,
                    health=self.health, place=self.place)


class Bee(Insect):
    """
    A Bee moves from place to place, following destinations and stinging ants.
    """

    def __init__(self, health, damage, delay):
        """
        Create a Bee with the given health and damage and make it wait for
        delay turns before acting.
        """
        super(Bee, self).__init__(UnitType.BEE, health, damage)
        self.delay = delay

    def fly(self):
        """
        Move from the Bee's current Place to a destination of that Place.
        """
        if len(self.place.destinations) > 0:
            destination = choice(self.place.destinations)
            self.place.remove_insect(self)
            destination.add_insect(self)

    def act(self, game_state):
        """
        A Bee stings the Ant that defends its place if it is blocked, but moves
        to a new place otherwise.  But a Bee cannot take any action if it is
        still delayed.
        """
        if self.delay > 0:
            self.delay -= 1
        else:
            defender = self.place.get_defender()
            if defender is not None and defender.blocks():
                defender.reduce_health(self.damage)
            else:
                self.fly()


class Ant(Insect):
    """
    An Ant defends a place and does work for the colony.
    """

    def __init__(self, unit_type, food_cost, health=1, damage=0):
        """
        Create an Ant with the given type, cost, health, and damage.
        """
        super(Ant, self).__init__(unit_type, health, damage)
        self.food_cost = food_cost

    # noinspection PyMethodMayBeStatic
    def blocks(self):
        """
        Determine whether the Ant blocks Bees from advancing.
        """
        return True

    def get_target_place(self):
        """
        Return the Place that the Ant's throws are targeting, if any.
        """
        return None


class Harvester(Ant):
    """
    A Harvester produces a certain amount of food per turn for the colony.
    """

    def __init__(self, unit_type, food_cost, health, production):
        """
        Create a Harvester with the given type, cost, health and per-turn food
        production.
        """
        super(Harvester, self).__init__(unit_type, food_cost, health)
        self.production = production

    def act(self, game_state):
        """
        A Harvest produces food for the colony.
        """
        game_state.food += self.production


class Thrower(Ant):
    """
    A Thrower throws a leaf each turn at the nearest Bee in its range.
    """

    def __init__(self, unit_type, food_cost, health, damage, minimum_range=0,
                 maximum_range=float('inf')):
        """
        Create a Thrower with the given type, cost, health, and damage.

        A Thrower can only target bees at distances between its minimum range
        and maximum range, inclusive.  A range of 0 corresponds to the Place
        the Ant is in, a range of 1 corresponds to all places leading to there,
        etc.  Furthermore, Throwers can only target bees in the colony; they
        cannot, for instance, target bees still in the hive.
        """
        super(Thrower, self).__init__(unit_type, food_cost, health, damage)
        self.minimum_range = minimum_range
        self.maximum_range = maximum_range

    @staticmethod
    def _get_target_place(candidate, minimum_range, maximum_range):
        """
        Recursively identify the nearest Place with a targetable bee.  Only
        bees in the colony and between minimum_range and maximum_range steps,
        inclusive, of the candidate place are considered targetable.  (Note
        that all steps are counted equally, regardless of the world_x and
        world_y of the Places they connect.)
        """
        if isinstance(candidate, ColonyPlace) and len(candidate.bees) > 0 and \
                minimum_range <= 0 <= maximum_range:
            return candidate
        for source in candidate.sources:
            target = Thrower._get_target_place(source, minimum_range - 1,
                                               maximum_range - 1)
            if target is not None:
                return target
        return None

    def get_target_place(self):
        """
        Identify the nearest Place with a targetable bee.

        Given a network of Places:
        >>> z, a, b, c, d, e, f, g = [ColonyPlace(i, i) for i in range(7)] + \
            [Place(7, 7)]
        >>> a.connect_to(z)
        >>> b.connect_to(a)
        >>> c.connect_to(a)
        >>> d.connect_to(b)
        >>> e.connect_to(b)
        >>> f.connect_to(c)
        >>> g.connect_to(c)

        and a Thrower at one of those Places:
        >>> thrower = Thrower(UnitType.THROWER, 1, 1, 1)
        >>> a.add_insect(thrower)

        get_target_place will return None if there are no Bees that can reach
        the given Place:
        >>> z.add_insect(Bee(1, 1, 0))
        >>> thrower.get_target_place() is None
        True

        It will also return None if there are bees that can reach the Place,
        but these Bees are outside the colony:
        >>> g.add_insect(Bee(1, 1, 0))
        >>> thrower.get_target_place() is None
        True

        But if there is a Bee in the colony that can reach the Place, and that
        Bee is in range, that Bee's place will be returned:
        >>> d.add_insect(Bee(1, 1, 0))
        >>> thrower.get_target_place()
        ColonyPlace(4, 4)

        If there are multiple in-range Bees at different Places,
        get_target_place will ignore Places that can only be hit by "shooting
        through" a valid target:
        >>> b.add_insect(Bee(1, 1, 0))
        >>> thrower.get_target_place()
        ColonyPlace(2, 2)
        """
        return self._get_target_place(self.place, self.minimum_range, self.maximum_range)

    def _get_target_bee(self):
        """
        Choose a random Bee in the place that the Ant's throws are targeting,
        if any.
        """
        target = self.get_target_place()
        return choice(target.bees) if target is not None else None

    def _hit_bee(self, target_bee):
        """
        Apply the effect of a thrown leaf hitting a Bee.  Normally, the effect
        is damage to the bee, but specialized throwers might have other
        effects.
        """
        target_bee.reduce_health(self.damage)

    def act(self, game_state):
        """
        Throw a leaf at the nearest bee, if any.
        """
        target_bee = self._get_target_bee()
        if target_bee is not None:
            self._hit_bee(target_bee)


class GameOutcome(Enum):
    """
    A GameOutcome represents whether a game should continue or not and, if not,
    why.
    """
    UNRESOLVED = 'UNRESOLVED'
    LOSS = 'LOSS'
    WIN = 'WIN'


class GameState(object):
    """
    A GameState represents the state of an entire game: the layout of the world
    (including the Insects at each Place and their behaviors), the kinds of
    Ants available to the player, and the player's resources.

    Kinds of ants are represented by archetypes, Ant instances that do not
    participate in play themselves, but which are copied to create the Ants
    that do appear in the game.
    """

    def __init__(self, places, queen_place, ant_archetypes, food):
        """
        Construct a world from the given places, designating one place as the
        Bee's target, offer the player the given archetypes, and provide the
        player with the given amount of starting food.  The places may be (and
        usually should be) prepopulated with insects.
        """
        self.ant_archetypes = ant_archetypes
        self.places = places
        self.queen_place = queen_place
        self.food = food

    def get_ants(self):
        """
        Collect a list of all of the Ants deployed in the world.
        """
        return [place.get_defender() for place in self.places
                if place.get_defender() is not None]

    def get_bees(self):
        """
        Collect a list of all of the Bees deployed in the world.
        """
        return [bee for place in self.places for bee in place.bees]

    # noinspection PyMethodMayBeStatic
    def place_ant(self, ant_archetype, place):
        """
        Make a player move to place an Ant based on the given archetype at the
        given Place.  Return that Ant, or None if the Ant could not be placed.
        Ants can only be placed on empty Places.
        """
        if ant_archetype is None or place.get_defender() is not None or \
                len(place.bees) > 0 or self.food < ant_archetype.food_cost:
            return None
        self.food -= ant_archetype.food_cost
        ant = deepcopy(ant_archetype)
        place.add_insect(ant)
        return ant

    def sacrifice_ant(self, ant):
        """
        Make a player move to sacrifice (kill) an Ant.
        """
        if ant is not None:
            assert ant.place is not None, \
                'Cannot sacrifice {ant}, which is already dead'.format(ant=ant)
            assert any(place.get_defender() is ant for place in self.places), \
                'Cannot sacrifice {ant}, which belongs to a different game' \
                .format(ant=ant)
            ant.reduce_health(ant.health)

    def take_turn(self):
        """
        If possible, cause one turn of game time to pass.  During a turn, Ants
        act, and then any surviving Bees act.

        Return the GameOutcome, GameOutcome.UNRESOLVED if time passed, but
        GameOutcome.LOSS or GameOutcome.WIN if time could not pass because the
        game is over.
        """
        if len(self.queen_place.bees) > 0:
            return GameOutcome.LOSS
        if len(self.get_bees()) == 0:
            return GameOutcome.WIN
        for ant in self.get_ants():
            ant.act(self)
        for bee in self.get_bees():
            bee.act(self)
        return GameOutcome.UNRESOLVED


STANDARD_ANT_ARCHETYPES = (
    Harvester(UnitType.HARVESTER, food_cost=3, health=1, production=2),
    Thrower(UnitType.SHORT_THROWER, food_cost=3, health=1, damage=1,
            minimum_range=0, maximum_range=2),
    Thrower(UnitType.THROWER, food_cost=7, health=1, damage=1),
    Thrower(UnitType.LONG_THROWER, food_cost=3, health=1, damage=1,
            minimum_range=4),
    Ant(UnitType.WALL, food_cost=4, health=4),
)


def make_standard_hive(center_x, center_y, radius, wave_count=4, wave_size=2,
                       wave_growth=1, wave_interval=5, bee_health=4,
                       bee_damage=1):
    """
    Construct a list of Places to represent a Bee hive prepopulated with Bees
    that will attack in waves.  The hive Places are distributed uniformly in a
    square with the given center and radius.
    """
    hive = []
    for wave_index in range(wave_count):
        for bee_index in range(wave_size + wave_index * wave_growth):
            bee = Bee(bee_health, bee_damage, wave_index * wave_interval)
            hive_place = Place(center_x + uniform(-radius, radius),
                               uniform(max(center_y - radius, 0),
                                       center_y + radius))
            hive_place.add_insect(bee)
            hive.append(hive_place)
    return hive


def make_standard_game(minimum_row_count=2, maximum_row_count=4,
                       column_count=9, wave_count=4, wave_size=2,
                       wave_growth=1, wave_interval=5, bee_health=4,
                       bee_damage=1, ant_archetypes=STANDARD_ANT_ARCHETYPES,
                       food=4):
    """
    Construct the GameState for the beginning of a standard game, which has the
    ant queen and the Bee's hive separated by tunnels of ColonyPlaces and Bee's
    attacking in waves of increasing size.  Most of the specifics of this setup
    can be varied by specifying non-default arguments.
    """
    assert minimum_row_count > 0, 'Cannot create a game with no rows'
    assert maximum_row_count >= minimum_row_count, \
        'The maximum row count must be at least the minimum row count'
    assert column_count > 0, 'Cannot create a game with no columns'

    center_y = (maximum_row_count + 1) / 2
    queen_place = Place(1, center_y)

    multiplier = maximum_row_count - minimum_row_count + 1
    heights = [int(minimum_row_count + multiplier * column / column_count)
               for column in range(column_count)]

    hive_center_x = 6 + column_count + heights[-1] - minimum_row_count
    hive = make_standard_hive(hive_center_x, center_y, 2, wave_count,
                              wave_size, wave_growth, wave_interval,
                              bee_health, bee_damage)

    tunnels = {}
    for column in range(column_count):
        height = heights[column]
        x = 3 + column + height - minimum_row_count
        for row in range(height):
            y = center_y + row - (height - 1) / 2
            place = Respite(x, y) if (column + 2 * row) % 5 == 1 else ColonyPlace(x, y)
            if column == 0:
                place.connect_to(queen_place)
            elif height == heights[column - 1]:
                place.connect_to(tunnels[column - 1, row])
            else:
                for other_row in range(heights[column - 1]):
                    place.connect_to(tunnels[column - 1, other_row])
            if column == column_count - 1:
                for hive_place in hive:
                    hive_place.connect_to(place)
            tunnels[column, row] = place
    return GameState([queen_place] + hive + list(tunnels.values()), queen_place, ant_archetypes, food)
