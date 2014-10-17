# This file is part of LiSE, a framework for life simulation games.
# Copyright (c) 2013-2014 Zachary Spector,  zacharyspector@gmail.com
from types import FunctionType
from marshal import loads as unmarshalled
from marshal import dumps as marshalled
from gorm.json import json_dump, json_load

alchemyOpError = None
try:
    from sqlalchemy.exc import OperationalError as alchemyOpError
except ImportError:
    pass
from sqlite3 import OperationalError as liteOpError
OperationalError = (alchemyOpError, liteOpError)

alchemyIntegError = None
try:
    from sqlalchemy.exc import IntegrityError as alchemyIntegError
except ImportError:
    pass
from sqlite3 import IntegrityError as liteIntegError
IntegrityError = (alchemyIntegError, liteIntegError)

import gorm.query
import LiSE.sql


class QueryEngine(gorm.query.QueryEngine):
    def sql(self, stringname, *args, **kwargs):
        if hasattr(LiSE.sql, stringname):
            return self.connection.cursor().execute(
                getattr(LiSE.sql, stringname).format_map(kwargs), args
            )
        return super().sql(stringname, *args)

    def count_all_table(self, tbl):
        return self.sql('count_all_fmt', tbl=tbl).fetchone()[0]

    def init_func_table(self, tbl):
        try:
            return self.sql('count_all_fmt', tbl=tbl)
        except OperationalError:
            return self.sql('func_store_create_table_fmt', tbl=tbl)

    def func_table_items(self, tbl):
        return self.sql('func_table_items_fmt', tbl=tbl)

    def func_table_contains(self, tbl, key):
        for row in self.sql('func_table_get_fmt', key, tbl=tbl):
            return True

    def func_table_get(self, tbl, key):
        bytecode = self.sql('func_table_get_fmt', key, tbl=tbl).fetchone()
        if bytecode is None:
            raise KeyError("No such function")
        return FunctionType(
            unmarshalled(bytecode[0]),
            globals()
        )

    def func_table_set(self, tbl, key, code):
        m = marshalled(code)
        try:
            return self.sql('func_table_ins_fmt', key, m, tbl=tbl)
        except IntegrityError:
            return self.sql('func_table_upd_fmt', m, key, tbl=tbl)

    def func_table_del(self, tbl, key):
        return self.sql('func_table_del_fmt', key, tbl=tbl)

    def init_string_table(self, tbl):
        try:
            return self.sql('count_all_fmt', tbl=tbl)
        except OperationalError:
            return self.sql('string_store_create_table_fmt', tbl=tbl)

    def string_table_lang_items(self, tbl, lang):
        return self.sql('string_table_lang_items_fmt', lang, tbl=tbl)

    def string_table_get(self, tbl, lang, key):
        for row in self.sql('string_table_get_fmt', lang, key, tbl=tbl):
            return row[0]

    def string_table_set(self, tbl, lang, key, value):
        try:
            self.sql('string_table_ins_fmt', key, lang, value, tbl=tbl)
        except IntegrityError:
            self.sql('string_table_upd_fmt', value, lang, key, tbl=tbl)

    def string_table_del(self, tbl, lang, key):
        self.sql('string_table_del_fmt', lang, key, tbl=tbl)

    def universal_items(self, branch, tick):
        seen = set()
        for (b, t) in self.active_branches(branch, tick):
            for (k, v) in self.sql('universal_items', branch, tick):
                if k not in seen and v is not None:
                    yield (json_load(k), json_load(v))
                seen.add(k)

    def universal_get(self, key, branch, tick):
        key = json_dump(key)
        for (b, t) in self.active_branches(branch, tick):
            for (v,) in self.sql('universal_get', key, b, t):
                if v is None:
                    raise KeyError("Key not set")
                return json_load(v)
        raise KeyError("Key never set")

    def universal_set(self, key, branch, tick, value):
        (key, value) = map(json_dump, (key, value))
        try:
            return self.sql('universal_ins', key, branch, tick, value)
        except IntegrityError:
            return self.sql('universal_upd', value, key, branch, tick)

    def universal_del(self, key, branch, tick):
        key = json_dump(key)
        try:
            return self.sql('universal_ins', key, branch, tick, None)
        except IntegrityError:
            return self.sql('universal_upd', None, key, branch, tick)

    def characters(self):
        for (ch,) in self.sql('characters'):
            yield json_load(ch)

    def ct_characters(self):
        return self.sql('ct_characters').fetchone()[0]

    def have_character(self, name):
        return bool(self.sql('ct_character', name))

    def del_character(self, name):
        name = json_dump(name)
        self.sql('del_char_things', name)
        self.sql('del_char_avatars', name)
        for tbl in (
                "node_val",
                "edge_val",
                "edges",
                "nodes",
                "graph_val",
                "characters",
                "graph"
        ):
            self.sql('char_del_fmt', name, tbl=tbl)

    def active_rules_rulebook(self, rulebook, branch, tick):
        seen = set()
        for (b, t) in self.active_branches(branch, tick):
            for (rule, active) in self.sql(
                    'active_rules_rulebook', rulebook, branch, tick
            ):
                if active and rule not in seen:
                    yield rule
                seen.add(rule)

    def active_rules_except_rulebooks(self, rulebooks, branch, tick):
        qms = ", ".join("?" for book in rulebooks)
        seen = set()
        for (b, t) in self.active_branches(branch, tick):
            for (rule, active) in self.sql(
                    branch,
                    tick,
                    *rulebooks,
                    qms=qms
            ):
                if active and rule not in seen:
                    yield rule
                seen.add(rule)

    def active_rule_rulebook(self, rulebook, rule, branch, tick):
        for (b, t) in self.active_branches(branch, tick):
            for (active,) in self.sql(
                    'active_rule_rulebook', rulebook, rule, branch, tick
            ):
                return bool(active)
        return False

    def active_rules_char(self, tbl, character, rulebook, branch, tick):
        character = json_dump(character)
        seen = set()
        for (b, t) in self.active_branches(branch, tick):
            for (rule, active) in self.sql(
                    'active_rules_char_fmt', character, rulebook, b, t, tbl=tbl
            ):
                if active and rule not in seen:
                    yield rule
                seen.add(rule)

    def active_rule_char(self, tbl, character, rulebook, rule, branch, tick):
        character = json_dump(character)
        for (b, t) in self.active_branches(branch, tick):
            for (active,) in self.sql(
                    'active_rule_char_fmt',
                    character,
                    rulebook,
                    rule,
                    b,
                    t,
                    tbl=tbl
            ):
                return bool(active)
        return False

    def rule_set(self, rulebook, rule, branch, tick, active):
        try:
            self.sql(
                'rule_ins_fmt', rulebook, rule, branch, tick, active
            )
        except IntegrityError:
            self.sql(
                'rule_upd_fmt', active, rulebook, rule, branch, tick
            )

    def poll_char_rules(self, branch, tick):
        # character rules
        for rulemap in ('character', 'avatar', 'thing', 'place', 'portal'):
            seen = set()
            for (b, t) in self.active_branches(branch, tick):
                for (c, rulebook, rule, active) in self.sql(
                        'poll_char_rules_fmt', b, t, b, t, tbl=rulemap
                ):
                    if (c, rulebook, rule) in seen:
                        continue
                    seen.add((c, rulebook, rule))
                    if active:
                        yield (rulemap, json_load(c), rulebook, rule)

    def poll_node_rules(self, branch, tick):
        seen = set()
        for (b, t) in self.active_branches(branch, tick):
            for (c, n, rulebook, rule, active) in self.sql(
                    'poll_node_rules', b, t, b, t
            ):
                if (c, n, rulebook, rule) in seen:
                    continue
                seen.add((c, n, rulebook, rule))
                if active:
                    yield (json_load(c), json_load(n), rulebook, rule)

    def handled_rule(self, ruletyp, character, rulebook, rule, branch, tick):
        character = json_dump(character)
        return self.sql(
            'handled_rule_fmt',
            character,
            rulebook,
            rule,
            branch,
            tick,
            ruletyp=ruletyp
        )

    def handled_node_rule(self, character, node, rulebook, rule, branch, tick):
        (character, node) = map(json_dump, (character, node))
        self.sql(
            'node_rule_handled',
            character,
            node,
            rulebook,
            rule,
            branch,
            tick
        )

    def node_is_thing(self, character, node, branch, tick):
        (character, node) = map(json_dump, (character, node))
        for (b, t) in self.active_branches(branch, tick):
            for (loc,) in self.sql(
                    'node_is_thing', character, node, branch, tick
            ):
                return bool(loc)
        return False

    def get_rulebook_char(self, rulemap, character):
        character = json_dump(character)
        for (book,) in self.sql(
                'rulebook_get_char_fmt', character, rulemap=rulemap
        ):
            return book
        raise KeyError("No rulebook")

    def upd_rulebook_char(self, rulemap, character):
        character = json_dump(character)
        return self.sql('upd_rulebook_char_fmt', character, rulemap=rulemap)

    def node_rulebook_get(self, character, node):
        (character, node) = map(json_dump, (character, node))
        try:
            return self.sql('node_rulebook_get', character, node).fetchone()[0]
        except TypeError:
            return None

    def node_rulebook_set(self, character, node, rulebook):
        (character, node) = map(json_dump, (character, node))
        try:
            self.sql('node_rulebook_ins', character, node, rulebook)
        except IntegrityError:
            self.sql('node_rulebook_upd', rulebook, character, node)

    def avatar_users(self, graph, node, branch, tick):
        (graph, node) = map(json_dump, (graph, node))
        seen = set()
        for (b, t) in self.active_branches(branch, tick):
            for (av_g,) in self.sql('avatar_users', graph, node, b, t):
                if av_g not in seen:
                    yield json_load(av_g)

    def arrival_time_get(self, character, thing, location, branch, tick):
        (character, thing, location) = map(
            json_dump, (character, thing, location)
        )
        for (b, t) in self.active_branches(branch, tick):
            for hitick in self.sql(
                    'arrival_time_get',
                    character,
                    thing,
                    location,
                    b,
                    t
            ):
                return hitick
        raise ValueError("No arrival time recorded")

    def next_arrival_time_get(self, character, thing, location, branch, tick):
        (character, thing, location) = map(
            json_dump, (character, thing, location)
        )
        for (b, t) in self.active_branches(branch, tick):
            for (hitick,) in self.sql(
                    'next_arrival_time_get',
                    character,
                    thing,
                    location,
                    branch,
                    tick
            ):
                return hitick
        return None

    def thing_loc_and_next_get(self, character, thing, branch, tick):
        (character, thing) = map(json_dump, (character, thing))
        for (b, t) in self.active_branches(branch, tick):
            for (loc, nextloc) in self.sql(
                    'thing_loc_and_next_get', character, thing, b, t
            ):
                return (json_load(loc), json_load(nextloc))

    def thing_loc_and_next_set(
            self, character, thing, branch, tick, loc, nextloc
    ):
        (character, thing, loc) = map(
            json_dump,
            (character, thing, loc)
        )
        nextloc = json_dump(nextloc) if nextloc else None
        try:
            return self.sql(
                'thing_loc_and_next_ins',
                character,
                thing,
                branch,
                tick,
                loc,
                nextloc
            )
        except IntegrityError:
            return self.sql(
                'thing_loc_and_next_upd',
                loc,
                nextloc,
                character,
                thing,
                branch,
                tick
            )

    def thing_loc_and_next_del(self, character, thing, branch, tick):
        (character, thing) = map(json_dump, (character, thing))
        try:
            self.sql(
                'thing_loc_and_next_ins',
                character,
                thing,
                branch,
                tick,
                None,
                None
            )
        except IntegrityError:
            self.sql(
                'thing_loc_and_next_upd',
                None,
                None,
                character,
                thing,
                branch,
                tick
            )

    def thing_loc_items(self, character, branch, tick):
        character = json_dump(character)
        seen = set()
        for (b, t) in self.active_branches(branch, tick):
            for (n, l) in self.sql(
                    'thing_loc_items',
                    character,
                    b,
                    t,
                    character,
                    b,
                    t
            ):
                if l is not None and n not in seen:
                    yield (json_load(n), json_load(l))
                seen.add(n)

    def thing_and_loc(self, character, thing, branch, tick):
        (character, thing) = map(json_dump, (character, thing))
        for (b, t) in self.active_branches(branch, tick):
            for (th, l) in self.sql(
                    'thing_and_loc',
                    character,
                    thing,
                    b,
                    t,
                    character,
                    thing,
                    b,
                    t
            ):
                if l is None:
                    raise KeyError("Thing does not exist")
                return (json_load(th), json_load(l))
        raise KeyError("Thing never existed")

    def character_things_items(self, character, branch, tick):
        character = json_dump(character)
        seen = set()
        for (b, t) in self.active_branches(branch, tick):
            for (th, l) in self.sql(
                    'character_things_items', character, b, t
            ):
                if l is not None and th not in seen:
                    yield (json_load(th), json_load(l))
                seen.add(th)

    def avatarness(self, character, branch, tick):
        character = json_dump(character)
        d = {}
        for (b, t) in self.active_branches(branch, tick):
            for (graph, node, avatar) in self.sql(
                    'avatarness', character, b, t
            ):
                g = json_load(graph)
                n = json_load(node)
                is_av = bool(avatar)
                if g not in d:
                    d[g] = {}
                d[g][n] = is_av
        return d

    def is_avatar_of(self, character, graph, node, branch, tick):
        (character, graph, node) = map(json_dump, (character, graph, node))
        for (avatarness,) in self.sql(
                'is_avatar_of', character, graph, node, branch, tick
        ):
            return avatarness and self.node_exists(
                graph, node, branch, tick
            )

    def sense_func_get(self, character, sense, branch, tick):
        character = json_dump(character)
        for (b, t) in self.active_branches(branch, tick):
            for (func,) in self.sql(
                    'sense_func_get', character, sense, branch, tick
            ):
                return func

    def sense_active_items(self, character, branch, tick):
        character = json_dump(character)
        seen = set()
        for (b, t) in self.active_branches(branch, tick):
            for (sense, active) in self.sql(
                    'sense_active_items', character, b, t
            ):
                if sense not in seen and active:
                    yield sense
                seen.add(sense)

    def sense_is_active(self, character, sense, branch, tick):
        character = json_dump(character)
        for (b, t) in self.active_branches(branch, tick):
            for (act,) in self.sql(
                    'sense_is_active', character, sense, branch, tick
            ):
                return bool(act)
        return False

    def sense_fun_set(self, character, sense, branch, tick, funn, active):
        character = json_dump(character)
        try:
            self.sql(
                'sense_fun_ins', character, sense, branch, tick, funn, active
            )
        except IntegrityError:
            self.sql(
                'sense_fun_upd', funn, active, character, sense, branch, tick
            )

    def sense_set(self, character, sense, branch, tick, active):
        character = json_dump(character)
        try:
            self.sql('sense_ins', character, sense, branch, tick, active)
        except IntegrityError:
            self.sql('sense_upd', active, character, sense, branch, tick)

    def init_character(
            self, character, charrule, avrule, thingrule, placerule, portrule
    ):
        character = json_dump(character)
        try:
            return self.sql(
                'character_ins',
                character,
                charrule,
                avrule,
                thingrule,
                placerule,
                portrule
            )
        except IntegrityError:
            pass

    def avatars_now(self, character, branch, tick):
        character = json_dump(character)
        seen = set()
        for (b, t) in self.active_branches(branch, tick):
            for (g, n, a) in self.sql('avatars_now', character, b, t, b, t):
                if (g, n) not in seen:
                    yield (json_load(g), json_load(n), a)
                seen.add((g, n))

    def avatars_ever(self, character):
        character = json_dump(character)
        for (g, n, b, t, a) in self.sql('avatars_ever', character):
            yield (json_load(g), json_load(n), b, t, a)

    def avatar_set(self, character, graph, node, branch, tick, isav):
        (character, graph, node) = map(json_dump, (character, graph, node))
        try:
            return self.sql(
                'avatar_ins', character, graph, node, branch, tick, isav
            )
        except IntegrityError:
            return self.sql(
                'avatar_upd', isav, character, graph, node, branch, tick
            )

    def rulebook_set(self, rulebook, idx, rule):
        try:
            return self.sql('rulebook_ins', rulebook, idx, rule)
        except IntegrityError:
            return self.sql('rulebook_upd', rule, rulebook, idx)

    def rulebook_decr(self, rulebook, idx):
        self.sql('rulebook_dec', rulebook, idx)

    def rulebook_del(self, rulebook, idx):
        self.sql('rulebook_del', rulebook, idx)
        self.sql('rulebook_dec', rulebook, idx)

    def rulebook_rules(self, rulebook):
        for (rule,) in self.sql('rulebook_rules', rulebook):
            yield rule

    def ct_rulebook_rules(self, rulebook):
        return self.sql('ct_rulebook_rules', rulebook).fetchone()[0]

    def rulebook_get(self, rulebook, idx):
        return self.sql('rulebook_get', rulebook, idx).fetchone()[0]

    def allrules(self):
        for (rule,) in self.sql('allrules'):
            yield rule

    def ctrules(self):
        return self.sql('ctrules').fetchone()[0]

    def ruledel(self, rule):
        self.sql('ruledel', rule)

    def haverule(self, rule):
        for r in self.sql('haverule', rule):
            return True
        return False

    def ruleins(self, rule):
        self.sql('ruleins', rule)

    def avatar_branch_data(self, character, graph, branch, tick):
        (character, graph) = map(json_dump, (character, graph))
        for (node, isav) in self.sql(
                'avatar_branch_data', character, graph, branch, tick
        ):
            yield (json_load(node), bool(isav))

    def thing_locs_data(self, character, thing, branch):
        (character, thing) = map(json_dump, (character, thing))
        for (tick, loc, nextloc) in self.sql(
                'thing_locs_data', character, thing, branch
        ):
            yield (tick, json_load(loc), json_load(nextloc))

    def initdb(self):
        """Set up the database schema, both for gorm and the special
        extensions for LiSE

        """
        super().initdb()
        cursor = self.connection.cursor()
        try:
            cursor.execute('SELECT * FROM lise_globals;')
        except OperationalError:
            cursor.execute(
                "CREATE TABLE lise_globals ("
                "key TEXT NOT NULL, "
                "branch TEXT NOT NULL DEFAULT 'master', "
                "tick INTEGER NOT NULL DEFAULT 0, "
                "value TEXT, "
                "PRIMARY KEY(key, branch, tick))"
                ";"
            )
        try:
            cursor.execute('SELECT * FROM rules;')
        except OperationalError:
            cursor.execute(
                "CREATE TABLE rules ("
                "rule TEXT NOT NULL PRIMARY KEY, "
                "actions TEXT NOT NULL DEFAULT '[]', "
                "prereqs TEXT NOT NULL DEFAULT '[]', "
                "triggers TEXT NOT NULL DEFAULT '[]')"
                ";"
            )
        try:
            cursor.execute('SELECT * FROM rulebooks;')
        except OperationalError:
            cursor.execute(
                "CREATE TABLE rulebooks ("
                "rulebook TEXT NOT NULL, "
                "idx INTEGER NOT NULL, "
                "rule TEXT NOT NULL, "
                "PRIMARY KEY(rulebook, idx), "
                "FOREIGN KEY(rule) REFERENCES rules(rule))"
                ";"
            )
        try:
            cursor.execute('SELECT * FROM active_rules;')
        except OperationalError:
            cursor.execute(
                "CREATE TABLE active_rules ("
                "rulebook TEXT NOT NULL, "
                "rule TEXT NOT NULL, "
                "branch TEXT NOT NULL DEFAULT 'master', "
                "tick INTEGER NOT NULL DEFAULT 0, "
                "active BOOLEAN NOT NULL DEFAULT 1, "
                "PRIMARY KEY(rulebook, rule, branch, tick), "
                "FOREIGN KEY(rulebook, rule) "
                "REFERENCES rulebooks(rulebook, rule))"
                ";"
            )
            cursor.execute(
                "CREATE INDEX active_rules_idx ON active_rules(rulebook, rule)"
                ";"
            )
        try:
            cursor.execute('SELECT * FROM characters;')
        except OperationalError:
            cursor.execute(
                "CREATE TABLE characters ("
                "character TEXT NOT NULL PRIMARY KEY, "
                "character_rulebook TEXT NOT NULL, "
                "avatar_rulebook TEXT NOT NULL, "
                "thing_rulebook TEXT NOT NULL, "
                "place_rulebook TEXT NOT NULL, "
                "portal_rulebook TEXT NOT NULL, "
                "FOREIGN KEY(character) REFERENCES graphs(graph))"
                ";"
            )
        try:
            cursor.execute('SELECT * FROM senses;')
        except OperationalError:
            cursor.execute(
                "CREATE TABLE senses ("
                "character TEXT, "
                # null means every character has this sense
                "sense TEXT NOT NULL, "
                "branch TEXT NOT NULL DEFAULT 'master', "
                "tick INTEGER NOT NULL DEFAULT 0, "
                "function TEXT NOT NULL, "
                "active BOOLEAN NOT NULL DEFAULT 1, "
                "PRIMARY KEY(character, sense, branch, tick),"
                "FOREIGN KEY(character) REFERENCES graphs(graph))"
                ";"
            )
            cursor.execute(
                "CREATE INDEX senses_idx ON senses(character, sense)"
                ";"
            )
        try:
            cursor.execute('SELECT * FROM travel_reqs;')
        except OperationalError:
            cursor.execute(
                "CREATE TABLE travel_reqs ("
                "character TEXT NOT NULL DEFAULT '', "
                # empty string means these are required of every character
                "branch TEXT NOT NULL DEFAULT 'master', "
                "tick INTEGER NOT NULL DEFAULT 0, "
                "reqs TEXT NOT NULL DEFAULT '[]', "
                "PRIMARY KEY(character, branch, tick), "
                "FOREIGN KEY(character) REFERENCES graphs(graph))"
                ";"
            )
            cursor.execute(
                "CREATE INDEX travel_reqs_idx ON travel_reqs(character)"
                ";"
            )
        try:
            cursor.execute('SELECT * FROM things;')
        except OperationalError:
            cursor.execute(
                "CREATE TABLE things ("
                "character TEXT NOT NULL, "
                "thing TEXT NOT NULL, "
                "branch TEXT NOT NULL DEFAULT 'master', "
                "tick INTEGER NOT NULL DEFAULT 0, "
                "location TEXT, "  # when null, I'm not a thing; treat
                # me like any other node
                "next_location TEXT, "  # when set, indicates that I'm
                # en route between location and
                # next_location
                "PRIMARY KEY(character, thing, branch, tick), "
                "FOREIGN KEY(character, thing) REFERENCES nodes(graph, node), "
                "FOREIGN KEY(character, location) "
                "REFERENCES nodes(graph, node))"
                ";"
            )
            cursor.execute(
                "CREATE INDEX things_idx ON things(character, thing)"
                ";"
            )
        try:
            cursor.execute('SELECT * FROM node_rulebook;')
        except OperationalError:
            cursor.execute(
                "CREATE TABLE node_rulebook ("
                "character TEXT NOT NULL, "
                "node TEXT NOT NULL, "
                "rulebook TEXT NOT NULL, "
                "PRIMARY KEY(character, node), "
                "FOREIGN KEY(character, node) REFERENCES nodes(graph, node))"
                ";"
            )
        try:
            cursor.execute('SELECT * FROM avatars;')
        except OperationalError:
            cursor.execute(
                "CREATE TABLE avatars ("
                "character_graph TEXT NOT NULL, "
                "avatar_graph TEXT NOT NULL, "
                "avatar_node TEXT NOT NULL, "
                "branch TEXT NOT NULL DEFAULT 'master', "
                "tick INTEGER NOT NULL DEFAULT 0, "
                "is_avatar BOOLEAN NOT NULL, "
                "PRIMARY KEY("
                "character_graph, "
                "avatar_graph, "
                "avatar_node, "
                "branch, "
                "tick"
                "), "
                "FOREIGN KEY(character_graph) REFERENCES graphs(graph), "
                "FOREIGN KEY(avatar_graph, avatar_node) "
                "REFERENCES nodes(graph, node))"
                ";"
            )
            cursor.execute(
                "CREATE INDEX avatars_idx ON avatars("
                "character_graph, "
                "avatar_graph, "
                "avatar_node)"
                ";"
            )
        try:
            cursor.execute("SELECT * FROM node_rules_handled;")
        except OperationalError:
            cursor.execute(
                "CREATE TABLE node_rules_handled ("
                "character TEXT NOT NULL, "
                "node TEXT NOT NULL, "
                "rulebook TEXT NOT NULL, "
                "rule TEXT NOT NULL, "
                "branch TEXT NOT NULL DEFAULT 'master', "
                "tick INTEGER NOT NULL DEFAULT 0, "
                "PRIMARY KEY(character, node, rule, branch, tick), "
                "FOREIGN KEY(character, node) "
                "REFERENCES nodes(graph, node))"
                ";"
            )
        handled = (
            "CREATE TABLE {table}_rules_handled ("
            "character TEXT NOT NULL, "
            "rulebook TEXT NOT NULL, "
            "rule TEXT NOT NULL, "
            "branch TEXT NOT NULL DEFAULT 'master', "
            "tick INTEGER NOT NULL DEFAULT 0, "
            "PRIMARY KEY(character, rulebook, rule, branch, tick), "
            "FOREIGN KEY(character, rulebook) "
            "REFERENCES characters(character, {table}_rulebook))"
            ";"
        )
        handled_idx = (
            "CREATE INDEX {table}_rules_handled_idx ON "
            "{table}_rules_handled(character, rulebook, rule)"
            ";"
        )
        rulesview = (
            "CREATE VIEW {table}_rules AS "
            "SELECT character, rulebook, rule, branch, tick, active "
            "FROM active_rules JOIN characters ON "
            "active_rules.rulebook=characters.{table}_rulebook"
            ";"
        )
        for tabn in ("character", "avatar", "thing", "place", "portal"):
            try:
                cursor.execute(
                    'SELECT * FROM {tab}_rules_handled;'.format(tab=tabn)
                )
            except OperationalError:
                cursor.execute(
                    handled.format(table=tabn)
                )
                cursor.execute(
                    handled_idx.format(table=tabn)
                )
                cursor.execute(
                    rulesview.format(table=tabn)
                )
