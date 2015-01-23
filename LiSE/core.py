# This file is part of LiSE, a framework for life simulation games.
# Copyright (c) 2013-2014 Zachary Spector,  zacharyspector@gmail.com
"""Object relational mapper that serves Characters."""
from random import Random
from collections import (
    defaultdict,
    deque,
    Mapping,
    MutableMapping,
    Callable
)
from sqlite3 import connect
from gorm import ORM as gORM
from .character import Character
from .rule import AllRules
from .query import QueryEngine
from .util import dispatch, listen, listener, RedundantRuleError


class NotThatMap(Mapping):
    """Wraps another mapping and conceals exactly one of its keys."""
    def __init__(self, inner, k):
        self.inner = inner
        self.k = k

    def __iter__(self):
        for key in self.inner:
            if key != self.k:
                yield key

    def __len__(self):
        return len(self.inner) - 1

    def __getitem__(self, key):
        if key == self.k:
            raise KeyError("masked")
        return self.inner[key]


class StringStore(MutableMapping):
    """Store strings in database, and format them with one another upon retrieval.

    In any one string, putting the key of another string in curly
    braces will cause the other string to be substituted in.

    """
    def __init__(self, engine, table='strings', lang='eng'):
        """Store the engine, the name of the database table to use, and the
        language code.

        """
        self.engine = engine
        self.table = table
        self._language = lang
        self._lang_listeners = []
        self.cache = {}
        self._str_listeners = defaultdict(list)
        self.engine.db.init_string_table(table)

    def _dispatch_lang(self, v):
        for f in self._lang_listeners:
            f(self, v)

    def lang_listener(self, f):
        listen(self._lang_listeners, f)

    def _dispatch_str(self, k, v):
        dispatch(self._str_listeners, k, self, k, v)

    def listener(self, fun=None, string=None):
        return listener(self._str_listeners, fun, string)

    @property
    def language(self):
        return self._language

    @language.setter
    def language(self, v):
        """Invalidate the cache upon changing the language."""
        self._language = v
        self._dispatch_lang(v)
        self.cache = {}

    def __iter__(self):
        """First cache, then iterate over all string IDs for the current
        language.

        """
        for (k, v) in self.engine.db.string_table_lang_items(
                self.table, self.language
        ):
            self.cache[k] = v
        return iter(self.cache.keys())

    def __len__(self):
        """"Count strings in the current language."""
        return self.engine.db.count_all_table(self.table)

    def __getitem__(self, k):
        """Get the string and format it with other strings here."""
        if k not in self.cache:
            self.cache[k] = self.engine.db.string_table_get(
                self.table, self.language, k
            )
        return self.cache[k].format_map(NotThatMap(self, k))

    def __setitem__(self, k, v):
        """Set the value of a string for the current language."""
        self.cache[k] = v
        self.engine.db.string_table_set(self.table, self.language, k, v)
        self._dispatch_str(k, v)

    def __delitem__(self, k):
        """Delete the string from the current language, and remove it from the
        cache.

        """
        del self.cache[k]
        self.engine.db.string_table_del(self.table, self.language, k)
        self._dispatch_str(k, None)


class FunctionStoreDB(MutableMapping):
    """Store functions in a SQL database"""
    def __init__(self, engine, codedb, table):
        """Use ``codedb`` as a connection object. Connect to it, and
        initialize the schema if needed.

        """
        self.engine = engine
        self.connection = codedb
        self.db = QueryEngine(self.connection, [], False)
        self.db.init_table(table)
        self._tab = table
        self._listeners = defaultdict(list)
        self.cache = {}
        self.engine.db.init_func_table(table)

    def _dispatch(self, name, fun):
        dispatch(self._listeners, name, self, name, fun)

    def listener(self, f=None, name=None):
        return listener(self._listeners, f, name)

    def __len__(self):
        """SELECT COUNT(*) FROM {}""".format(self._tab)
        return self.db.count_all_table(self._tab)

    def __iter__(self):
        """SELECT name FROM {} ORDER BY name""".format(self._tab)
        return self.db.func_table_iter(self._tab)

    def __contains__(self, name):
        """Check if there's such a function in the database"""
        if name in self.cache:
            return True
        return self.db.func_table_contains(self._tab, name)

    def __getitem__(self, name):
        """Reconstruct the named function from its code string stored in the
        code database, and return it.

        """
        if name not in self.cache:
            self.cache[name] = self.db.func_table_get(self._tab, name)
        return self.cache[name]

    def __call__(self, fun):
        """Remember the function in the code database. Its key will be its
        ``__name__``.

        """
        if fun in self:
            raise KeyError(
                "Already have a function by that name. "
                "If you want to swap it out for this one, "
                "assign the new function to me like I'm a dictionary."
            )
        self.db.func_table_set(self._tbl, fun.__name__, fun)
        self.cache[fun.__name__] = fun
        self._dispatch(fun.__name__, fun)

    def __setitem__(self, name, fun):
        """Store the function, marshalled, under the name given."""
        self.db.func_table_set(self._tab, name, fun)
        self.cache[name] = fun
        self._dispatch(name, fun)

    def __delitem__(self, name):
        self.db.func_table_del(self._tab, name)
        del self.cache[name]
        self._dispatch(name, None)

    def decompiled(self, name):
        """Use unpyc3 to decompile the function named ``name`` and return the
        resulting unpyc3.DefStatement.

        unpyc3 is imported here, so if you never use this you don't
        need unpyc3.

        """
        from unpyc3 import decompile
        return decompile(self[name])

    def definition(self, name):
        """Return a string showing how the function named ``name`` was
        originally defined.

        It will be decompiled from the bytecode stored in the
        database. Requires unpyc3.

        """
        return str(self.decompiled(name))

    def commit(self):
        self.connection.commit()


class GlobalVarMapping(MutableMapping):
    """Mapping for variables that are global but which I keep history for"""
    def __init__(self, engine):
        """Store the engine"""
        self.engine = engine
        self._listeners = defaultdict(list)

    def _dispatch(self, k, v):
        dispatch(self._listeners, k, self, k, v)

    def listener(self, f=None, key=None):
        return listener(self._listeners, f, key)

    def __iter__(self):
        """Iterate over the global keys whose values aren't null at the moment.

        The values may be None, however.

        """
        for (k, v) in self.engine.db.universal_items(*self.engine.time):
            yield k

    def __len__(self):
        """Just count while iterating"""
        n = 0
        for k in iter(self):
            n += 1
        return n

    def __getitem__(self, k):
        """Get the current value of this key"""
        return self.engine.db.universal_get(k, *self.engine.time)

    def __setitem__(self, k, v):
        """Set k=v at the current branch and tick"""
        (branch, tick) = self.engine.time
        self.engine.db.universal_set(k, branch, tick, v)
        self._dispatch(k, v)

    def __delitem__(self, k):
        """Unset this key for the present (branch, tick)"""
        self.engine.db.universal_del(k)
        self._dispatch(k, None)


class CharacterMapping(MutableMapping):
    def __init__(self, engine):
        self.engine = engine
        self._listeners = defaultdict(list)
        self._cache = {}

    def _dispatch(self, k, v):
        dispatch(self._listeners, k, self, k, v)

    def listener(self, f=None, char=None):
        return listener(self._listeners, f, char)

    def __iter__(self):
        return self.engine.db.characters()

    def __contains__(self, name):
        return self.engine.db.have_character(name)

    def __len__(self):
        return self.engine.db.ct_characters()

    def __getitem__(self, name):
        if hasattr(self, '_cache'):
            if name not in self._cache:
                if name not in self:
                    raise KeyError("No such character")
                self._cache[name] = Character(self.engine, name)
            return self._cache[name]
        if name not in self:
            raise KeyError("No such character")
        return Character(self.engine, name)

    def __setitem__(self, name, value):
        if isinstance(value, Character):
            self._cache[name] = value
            return
        self._cache[name] = Character(self.engine, name, data=value)
        self._dispatch(name, self._cache[name])

    def __delitem__(self, name):
        if hasattr(self, '_cache') and name in self._cache:
            del self._cache[name]
        self.engine.db.del_character(name)
        self._dispatch(name, None)


class Engine(object):
    def __init__(
            self,
            worlddb,
            codedb,
            connect_args={},
            alchemy=False,
            caching=True,
            commit_modulus=None,
            random_seed=None,
            gettext=lambda s: s,
            dicecmp=lambda x, y: x <= y
    ):
        """Store the connections for the world database and the code database;
        set up listeners; and start a transaction

        """
        self.caching = caching
        self.commit_modulus = commit_modulus
        self.gettext = gettext
        self.dicecmp = dicecmp
        self.random_seed = random_seed
        self.codedb = connect(codedb)
        self.gorm = gORM(
            worlddb,
            connect_args=connect_args,
            alchemy=alchemy,
            query_engine_class=QueryEngine
        )
        self.time_listeners = []
        self.db = self.gorm.db
        self.string = StringStore(self)
        self.rule = AllRules(self)
        self.eternal = self.db.globl
        self.universal = GlobalVarMapping(self)
        self.character = CharacterMapping(self)
        # start the database
        self.stores = ('action', 'prereq', 'trigger', 'sense', 'function')
        for store in self.stores:
            setattr(self, store, FunctionStoreDB(self, self.codedb, store))
        if hasattr(self.gorm.db, 'alchemist'):
            self.worlddb = self.gorm.db.alchemist.conn.connection
        else:
            self.worlddb = self.gorm.db.connection
        self.db.initdb()
        self._existence = {}
        self._timestream = {'master': {}}
        self._branch_start = {}
        self._branches = {'master': self._timestream['master']}
        self._branch_parents = {}
        if self.caching:
            self.gorm._obranch = self.gorm.branch
            self.gorm._orev = self.gorm.rev
            self._active_branches_cache = []
            self.db.active_branches = self._active_branches
            todo = deque(self.db.timestream_data())
            while todo:
                (branch, parent, parent_tick) = working = todo.popleft()
                if branch == 'master':
                    continue
                if parent in self._branches:
                    assert(branch not in self._branches)
                    self._branches[parent][branch] = {}
                    self._branches[branch] = self._branches[parent][branch]
                    self._branch_parents['branch'] = parent
                    self._branch_start[branch] = parent_tick
                else:
                    todo.append(working)
        for n in self.db.characters():
            self.character[n] = Character(self, n)
        self._rules_iter = self._follow_rules()
        # set up the randomizer
        self.rando = Random()
        if 'rando_state' in self.universal:
            self.rando.setstate(self.universal['rando_state'])
        else:
            self.rando.seed(self.random_seed)
            self.universal['rando_state'] = self.rando.getstate()
        self.betavariate = self.rando.betavariate
        self.choice = self.rando.choice
        self.expovariate = self.rando.expovariate
        self.gammaraviate = self.rando.gammavariate
        self.gauss = self.rando.gauss
        self.getrandbits = self.rando.getrandbits
        self.lognormvariate = self.rando.lognormvariate
        self.normalvariate = self.rando.normalvariate
        self.paretovariate = self.rando.paretovariate
        self.randint = self.rando.randint
        self.random = self.rando.random
        self.randrange = self.rando.randrange
        self.sample = self.rando.sample
        self.shuffle = self.rando.shuffle
        self.triangular = self.rando.triangular
        self.uniform = self.rando.uniform
        self.vonmisesvariate = self.rando.vonmisesvariate
        self.weibullvariate = self.rando.weibullvariate

    def _node_exists(self, graph, node):
        """Version of gorm's ``_node_exists`` that caches stuff"""
        if not self.caching:
            return node in self.gorm.get_graph(graph).node
        (branch, rev) = self.time
        if graph not in self._existence:
            self._existence[graph] = {}
        if node not in self._existence[graph]:
            self._existence[graph][node] = {}
        if branch not in self._existence[graph][node]:
            self._existence[graph][node][branch] = {}
        d = self._existence[graph][node][branch]
        if rev not in d:
            try:
                d[rev] = d[max(k for k in d.keys() if k < rev)]
            except ValueError:
                d[rev] = self.db.node_exists(graph, node, branch, rev)
        return self._existence[graph][node][branch][rev]

    def coinflip(self):
        """Return True or False with equal probability."""
        return self.choice((True, False))

    def dice(self, n, d):
        """Roll ``n`` dice with ``d`` faces, and return a list of the
        results.

        """
        return [self.randint(1, d) for i in range(0, n)]

    def dice_check(self, n, d, target):
        """Roll ``n`` dice with ``d`` sides, sum them, compare the total to
        ``target``, and return the result.

        The comparison operation defaults to <=. You can specify a
        different one in the ``dicecmp`` argument to my
        constructor. If you need a different comparison for a
        particular roll, call ``sum(self.dice(n, d))`` and do your own
        comparison on the result.

        """
        return self.dicecmp(sum(self.dice(n, d)), target)

    def percent_chance(self, pct):
        """Given a ``pct``% chance of something happening right now, decide at
        random whether it actually happens, and return ``True`` or
        ``False`` as appropriate.

        Values not between 0 and 100 are treated as though they
        were 0 or 100, whichever is nearer.

        """
        if pct <= 0:
            return False
        if pct >= 100:
            return True
        return pct / 100 < self.random()

    def commit(self):
        """Commit to both the world and code databases, and begin a new
        transaction for the world database

        """
        if self.caching:
            self.gorm.branch = self.gorm._obranch
            self.gorm.rev = self.gorm._orev
        for store in self.stores:
            getattr(self, store).commit()
        self.gorm.commit()

    def close(self):
        if self.caching:
            self.gorm.branch = self.gorm._obranch
            self.gorm.rev = self.gorm._orev
        self.gorm.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def on_time(self, v):
        if not isinstance(v, Callable):
            raise TypeError("This is a decorator")
        self.time_listeners.append(v)

    @property
    def branch(self):
        return self.gorm.branch

    @branch.setter
    def branch(self, v):
        """Set my gorm's branch and call listeners"""
        (b, t) = self.time
        if self.caching:
            if v == b:
                return
            if v not in self._branches:
                parent = b
                child = v
                assert(parent in self._branches)
                self._branch_parents[child] = parent
                self._branches[parent][child] = {}
                self._branches[child] = self._branches[parent][child]
                self._branches_start[child] = t
            self.gorm._obranch = v
        else:
            self.gorm.branch = v
        if not hasattr(self, 'locktime'):
            for time_listener in self.time_listeners:
                time_listener(self, b, t, v, t)

    @property
    def tick(self):
        return self.gorm.rev

    @tick.setter
    def tick(self, v):
        """Update orm's tick, and call listeners"""
        (branch_then, tick_then) = self.time
        if self.caching:
            if v == self.tick:
                return
            self.gorm._orev = v
        else:
            self.gorm.rev = v
        if not hasattr(self, 'locktime'):
            for time_listener in self.time_listeners:
                time_listener(self, branch_then, tick_then, branch_then, v)

    @property
    def time(self):
        """Return tuple of branch and tick"""
        return (self.branch, self.tick)

    @time.setter
    def time(self, v):
        """Set my gorm's ``branch`` and ``tick``, and call listeners"""
        (branch_then, tick_then) = self.time
        (branch_now, tick_now) = v
        relock = hasattr(self, 'locktime')
        self.locktime = True
        # setting tick and branch in this order makes it practical to
        # track the timestream genealogy
        self.tick = tick_now
        self.branch = branch_now
        if not relock:
            del self.locktime
        if not hasattr(self, 'locktime'):
            for time_listener in self.time_listeners:
                time_listener(
                    self, branch_then, tick_then, branch_now, tick_now
                )

    def _active_branches(self, branch=None, tick=None):
        if not self.caching:
            yield from self.gorm._active_branches()
            return
        b = branch if branch else self.branch
        t = tick if tick else self.tick
        yield b, t
        while b in self._branch_parents:
            t = self._branch_start[b]
            b = self._branch_parents[b]
            yield b, t

    def _branch_descendants(self, branch=None):
        branch = branch if branch else self.branch
        if not self.caching:
            yield from self.db.branch_descendants(branch)
            return
        yield from self._branches[branch].keys()
        for child in self._branches[branch].keys():
            yield from self._branch_descendants(child)

    def _poll_rules(self):
        for (
                rulemap, character, rulebook, rule
        ) in self.db.poll_char_rules(*self.time):
            try:
                yield (
                    rulemap,
                    self.character[character],
                    None,
                    rulebook,
                    self.rule[rule]
                )
            except KeyError:
                continue
        for (
                character, node, rulebook, rule
        ) in self.db.poll_node_rules(*self.time):
            try:
                c = self.character[character]
                n = c.node[node]
            except KeyError:
                continue
            typ = 'thing' if hasattr(n, 'location') else 'place'
            yield typ, c, n, rulebook, self.rule[rule]
        for (
                character, a, b, i, rulebook, rule
        ) in self.db.poll_portal_rules(*self.time):
            try:
                c = self.character[character]
                yield 'portal', c.portal[a][b], rulebook, self.rule[rule]
            except KeyError:
                continue

    def _follow_rules(self):
        (branch, tick) = self.time
        for (typ, character, entity, rulebook, rule) in self._poll_rules():
            def follow(*args):
                print('Following {}...'.format(rule))
                return (rule(self, *args), rule.name, typ, rulebook)

            if typ in ('thing', 'place', 'portal'):
                yield follow(character, entity)
                if typ == 'thing':
                    self.db.handled_thing_rule(
                        character.name,
                        entity.name,
                        rulebook,
                        rule.name,
                        branch,
                        tick
                    )
                elif typ == 'place':
                    self.db.handled_place_rule(
                        character.name,
                        entity.name,
                        rulebook,
                        rule.name,
                        branch,
                        tick
                    )
                else:
                    self.db.handled_portal_rule(
                        character.name,
                        entity.origin.name,
                        entity.destination.name,
                        rulebook,
                        rule.name,
                        branch,
                        tick
                    )
            else:
                if typ == 'character':
                    yield follow(character)
                elif typ == 'avatar':
                    for avatar in character.avatars():
                        yield follow(character, avatar)
                elif typ == 'character_thing':
                    for thing in character.thing.values():
                        yield follow(character, thing)
                elif typ == 'character_place':
                    for place in character.place.values():
                        yield follow(character, place)
                elif typ == 'character_portal':
                    for portal in character.portal.values():
                        yield follow(character, portal)
                else:
                    raise ValueError('Unknown type of rule')
                self.db.handled_character_rule(
                    typ, character.name, rulebook, rule.name, branch, tick
                )

    def advance(self):
        """Follow the next rule, or if there isn't one, advance to the next
        tick.

        """
        try:
            r = next(self._rules_iter)
        except StopIteration:
            self.tick += 1
            self._rules_iter = self._follow_rules()
            self.universal['rando_state'] = self.rando.getstate()
            if self.commit_modulus and self.tick % self.commit_modulus == 0:
                self.gorm.commit()
            r = None
        return r

    def next_tick(self):
        """Call ``advance`` repeatedly, appending its results to a list until
        the tick has ended.  Return the list.

        """
        curtick = self.tick
        r = []
        while self.tick == curtick:
            r.append(self.advance())
        return r[:-1]

    def new_character(self, name, **kwargs):
        """Create and return a character"""
        self.add_character(name, **kwargs)
        return self.character[name]

    def add_character(self, name, data=None, **kwargs):
        """Create the Character so it'll show up in my `character` dict"""
        self.gorm.new_digraph(name, data, **kwargs)
        ch = Character(self, name)
        if data is not None:
            for a in data.adj:
                for b in data.adj[a]:
                    assert(
                        a in ch.adj and
                        b in ch.adj[a]
                    )
        if hasattr(self.character, '_cache'):
            self.character._cache[name] = ch

    def del_character(self, name):
        """Remove the Character from the database entirely"""
        self.db.del_character(name)
        self.gorm.del_graph(name)
        del self.character[name]

    def _is_thing(self, character, node):
        """Private utility function to find out if a node is a Thing or not.

        ``character`` argument must be the name of a character, not a
        Character object. Likewise ``node`` argument is the node's
        ID.

        """
        return self.db.node_is_thing(character, node, *self.time)
