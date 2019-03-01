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
        Create a connection between this Place and the one given; Bees will travel from this Place to the other one.
        """
        self.destinations.append(place)
        place.sources.append(self)

    def get_defender(self):  # pylint: disable=no-self-use
        """
        Return the ant defending this place, if any.
        """
        return None

    def add_insect(self, insect):
        """
        Add an Insect to this Place.

        A plain Place can only hold bees. There can be any number of Bees in a Place.
        """
        assert isinstance(insect, Bee), f'The place {self} cannot hold {insect} of the type {type(insect).__name__}'
        assert insect not in self.bees, f'The bee {insect} cannot be added to {self} twice'
        self.bees.append(insect)
        insect.place = self

    def remove_insect(self, insect):
        """
        Remove an Insect from this Place.
        """
        assert insect in self.bees, f'{insect} is not at {self} to be removed'
        self.bees.remove(insect)
        insect.place = None

    def __repr__(self):
        return f'{type(self).__name__}({self.world_x}, {self.world_y})'


class ColonyPlace(Place):
    """
    A ColonyPlace, unlike a regular Place, can hold an Ant and be the target of an Ant's attack.
    """

    def __init__(self, world_x, world_y):
        """
        Create a ColonyPlace at the given coordinates.
        """
        super().__init__(world_x, world_y)
        self.ant = None

    def get_defender(self):
        """
        Return the ant defending this place, if any.
        """
        return self.ant

    def add_insect(self, insect):
        """
        Add an Insect to this Place.

        There can be at most one Ant in a ColonyPlace. If add_insect tries to add more Ants than is allowed, an
        AssertionError is raised.

        There can be any number of Bees in a Place.
        """
        if isinstance(insect, Ant):
            assert self.ant is None, f'The place {self} cannot hold both {self.ant} and {insect}'
            self.ant = insect
            insect.place = self
        else:
            super().add_insect(insect)

    def remove_insect(self, insect):
        """
        Remove an Insect from this Place.
        """
        if isinstance(insect, Ant):
            assert insect is self.ant, f'The ant {insect} is not at {self} to be removed'
            self.ant = None
            insect.place = None
        else:
            super().remove_insect(insect)


class UnitType(Enum):
    """
    A UnitType represents how an Insect looks to the player.  It is possible for otherwise identical Insects to have
    different UnitTypes, and it is also possible for fundamentally different Insects to have the same UnitType.

    Any changes to this Enum should be accompanied by corresponding changes to the frontend in main.py and tower.kv.
    STANDARD_ANT_ARCHETYPES, which appears later in this file, may also be affected.
    """
    BEE = 'BEE'
    HARVESTER = 'HARVESTER'
    THROWER = 'THROWER'


class Insect(object):
    """
    An Insect, the base class of Ant and Bee, has health and damage and also a Place.
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
        Reduce health by amount, and remove the insect from its place if it has no health remaining.
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
        return f'{type(self).__name__}({self.unit_type}, {self.health}, {self.place})'


class Bee(Insect):
    """
    A Bee moves from place to place, following destinations and stinging ants.
    """

    def __init__(self, health, damage, delay):
        """
        Create a Bee with the given health and damage and make it wait for delay turns before acting.
        """
        super().__init__(UnitType.BEE, health, damage)
        self.delay = delay

    def fly(self):
        """
        Move from the Bee's current Place to the destination of that Place.  If there are multiple destinations, choose
        one at random.
        """
        if len(self.place.destinations) > 0:
            destination = choice(self.place.destinations)
            self.place.remove_insect(self)
            destination.add_insect(self)

    def act(self, game_state):
        """
        A Bee stings the Ant that defends its place and doesn't fly if it is blocked:
        >>> place = ColonyPlace(1, 0)
        >>> next_place = ColonyPlace(0, 0)
        >>> place.connect_to(next_place)
        >>> state = GameState(places=[place, next_place], queen_place=None, ant_archetypes=[], food=0)
        >>> ant = Ant(unit_type=None, food_cost=0, health=5)
        >>> place.add_insect(ant)
        >>> bee = Bee(health=1, damage=1, delay=0)
        >>> place.add_insect(bee)
        >>> bee.act(state)
        >>> ant.health
        4
        >>> bee.place
        ColonyPlace(1, 0)

        but moves to a new place otherwise:
        >>> place = ColonyPlace(1, 0)
        >>> next_place = ColonyPlace(0, 0)
        >>> place.connect_to(next_place)
        >>> state = GameState(places=[place, next_place], queen_place=None, ant_archetypes=[], food=0)
        >>> ant = Ant(unit_type=None, food_cost=0, health=5)
        >>> next_place.add_insect(ant)
        >>> bee = Bee(health=1, damage=1, delay=0)
        >>> place.add_insect(bee)
        >>> bee.act(state)
        >>> ant.health
        5
        >>> bee.place
        ColonyPlace(0, 0)

        However, a Bee cannot take any action if it is still delayed; its delay decreases instead:
        >>> place = ColonyPlace(1, 0)
        >>> next_place = ColonyPlace(0, 0)
        >>> place.connect_to(next_place)
        >>> state = GameState(places=[place, next_place], queen_place=None, ant_archetypes=[], food=0)
        >>> ant = Ant(unit_type=None, food_cost=0, health=5)
        >>> place.add_insect(ant)
        >>> bee = Bee(health=1, damage=1, delay=4)
        >>> place.add_insect(bee)
        >>> bee.act(state)
        >>> ant.health
        5
        >>> bee.place
        ColonyPlace(1, 0)
        >>> bee.delay
        3
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
        super().__init__(unit_type, health, damage)
        self.food_cost = food_cost

    # noinspection PyMethodMayBeStatic
    def blocks(self):  # pylint: disable=no-self-use
        """
        Determine whether the Ant blocks Bees from advancing.
        """
        return True

    def get_target_place(self):  # pylint: disable=no-self-use
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
        Create a Harvester with the given type, cost, health and per-turn food production.
        """
        super().__init__(unit_type, food_cost, health)
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

    def __init__(self, unit_type, food_cost, health, damage, ammo, minimum_range=0, maximum_range=0):
        """
        Create a Thrower with the given type, cost, health, and damage.

        A Thrower can only target bees at distances between its minimum range and maximum range, inclusive.  A range of
        0 corresponds to the Place the Ant is in, a range of 1 corresponds to all places leading to there, etc.
        Furthermore, Throwers can only target bees in the colony; they cannot, for instance, target bees still in the
        hive.
        """
        super().__init__(unit_type, food_cost, health, damage)
        self.ammo = ammo
        self.minimum_range = minimum_range
        self.maximum_range = maximum_range

    def get_target_place(self):
        """
        Identify the nearest Place with a targetable bee.  Only bees in the colony and between minimum_range and
        maximum_range steps, inclusive, of the candidate place are considered targetable.  (Note that all steps are
        counted equally, regardless of the world_x and world_y of the Places they connect.)  Break ties by ….
        """
        if self.maximum_range < 0:
            return None
        visited = set()
        worklist = [(self.place, 0)]
        while len(worklist) > 0:
            candidate, distance = worklist.pop(0)
            if self.minimum_range <= distance and isinstance(candidate, ColonyPlace) and len(candidate.bees) > 0:
                return candidate
            if candidate not in visited:
                visited.add(candidate)
                if distance + 1 <= self.maximum_range:
                    worklist.extend((source, distance + 1) for source in candidate.sources)
        return None

    def _get_target_bee(self):
        """
        Choose a random Bee in the place that the Ant's throws are targeting, if any.
        """
        target = self.get_target_place()
        return choice(target.bees) if target is not None else None

    def _hit_bee(self, target_bee):
        """
        Apply the effect of a thrown leaf hitting a Bee.  Normally, the effect is damage to the bee, but specialized
        throwers might have other effects.
        """
        target_bee.reduce_health(self.damage)

    def act(self, game_state):
        """
        If there is a Bee approaching this Ant, and it is in-range, consume one unit of ammo to throw a leaf at that bee
        and reduce its health:
        >>> # Placeholder

        But ignore any Bee that is out of range:
        >>> # Placeholder

        or that has already flown past this Ant:
        >>> # Placeholder

        If there are multiple in-range bees approaching, target the one that is nearest:
        >>> # Placeholder

        And when all of its ammo is consumed, kill the ant:
        >>> # Placeholder
        """
        target_bee = self._get_target_bee()
        if target_bee is not None:
            self._hit_bee(target_bee)
            self.ammo -= 1
            if self.ammo <= 0:
                self.reduce_health(self.health)


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
    A GameState represents the state of an entire game: the layout of the world (including the Insects at each Place and
    their behaviors), the kinds of Ants available to the player, and the player's resources.

    Kinds of ants are represented by archetypes, Ant instances that do not participate in play themselves, but which are
    copied to create the Ants that do appear in the game.
    """

    def __init__(self, places, queen_place, ant_archetypes, food):
        """
        Construct a world from the given places, designating one place as the Bee's target, offer the player the given
        archetypes, and provide the player with the given amount of starting food.  The places may be (and usually
        should be) prepopulated with insects.
        """
        self.ant_archetypes = ant_archetypes
        self.places = places
        self.queen_place = queen_place
        self.food = food

    def get_ants(self):
        """
        Collect a list of all of the Ants deployed in the world.
        """
        return [place.get_defender() for place in self.places if place.get_defender() is not None]

    def get_bees(self):
        """
        Collect a list of all of the Bees deployed in the world.
        """
        return [bee for place in self.places for bee in place.bees]

    def place_ant(self, ant_archetype, place):
        """
        Make a player move to place an Ant based on the given archetype at the given Place.  Return that Ant, or None if
        the Ant could not be placed.  Ants can only be placed on empty Places.
        """
        if ant_archetype is None or place.get_defender() is not None or len(place.bees) > 0 or\
                self.food < ant_archetype.food_cost:
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
            assert ant.place is not None, f'Cannot sacrifice {ant}, which is already dead'
            assert any(place.get_defender() is ant for place in self.places),\
                f'Cannot sacrifice {ant}, which belongs to a different game'
            ant.reduce_health(ant.health)

    def take_turn(self):
        """
        If possible, cause one turn of game time to pass.  During a turn, Ants act, and then any surviving Bees act.

        Return the GameOutcome, GameOutcome.UNRESOLVED if time passed, but GameOutcome.LOSS or GameOutcome.WIN if time
        could not pass because the game is over.
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
    Harvester(UnitType.HARVESTER, food_cost=3, health=1, production=1),
    Thrower(UnitType.THROWER, food_cost=7, health=1, damage=1, ammo=4, minimum_range=0, maximum_range=2),
)


def make_standard_game(radius=4, wave_count=4, wave_size=2, wave_growth=1, wave_interval=5, bee_health=4, bee_damage=1,
                       ant_archetypes=STANDARD_ANT_ARCHETYPES, food=15):
    """
    Construct the GameState for the beginning of a standard game, which has the ant queen in the center of a square of
    ColonyPlaces, the Bee's hive on the periphery, and Bee's attacking in waves of increasing size.  Most of the
    specifics of this setup can be varied by specifying non-default arguments.
    """
    assert radius > 0, 'Cannot create a game with a nonpositive radius'

    side_length = 2 * radius + 1
    grid = [[ColonyPlace(x, y) for y in range(side_length)] for x in range(side_length)]
    queen_place = Place(radius, radius)
    # noinspection PyTypeChecker
    grid[radius][radius] = queen_place

    def distance_from(x, y):
        return max(abs(x - radius), abs(y - radius))

    boundary = []
    for x in range(side_length):
        for y in range(side_length):
            distance = distance_from(x, y)
            if distance == radius:
                boundary.append(grid[x][y])
            for adjacent_x in range(max(x - 1, 0), min(x + 2, side_length)):
                for adjacent_y in range(max(y - 1, 0), min(y + 2, side_length)):
                    if (adjacent_x, adjacent_y) != (x, y) and distance_from(adjacent_x, adjacent_y) <= distance:
                        grid[x][y].connect_to(grid[adjacent_x][adjacent_y])

    minimum_stretch = (radius + 1) / radius
    maximum_stretch = (radius + 3) / radius
    all_places = [place for column in grid for place in column]
    for wave_index in range(wave_count):
        for _ in range(wave_size + wave_index * wave_growth):
            bee = Bee(bee_health, bee_damage, wave_index * wave_interval)
            entrance = choice(boundary)
            hive_place = Place(uniform(minimum_stretch, maximum_stretch) * (entrance.world_x - radius) + radius,
                               uniform(minimum_stretch, maximum_stretch) * (entrance.world_y - radius) + radius)
            hive_place.add_insect(bee)
            hive_place.connect_to(entrance)
            # noinspection PyTypeChecker
            all_places.append(hive_place)

    x_shift = 1 - min(place.world_x for place in all_places)
    y_shift = 1 - min(place.world_y for place in all_places)
    for place in all_places:
        place.world_x += x_shift
        place.world_y += y_shift

    return GameState(all_places, queen_place, ant_archetypes, food)
