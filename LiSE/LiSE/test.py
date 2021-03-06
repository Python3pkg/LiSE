import unittest
import re
from functools import reduce
from collections import defaultdict
from allegedb.cache import StructuredDefaultDict, WindowDict
from LiSE.engine import Engine
from LiSE.examples import college as sim


def deepDictDiffIter(d0, d1, lvl=0):
    tabs = "\t" * lvl
    if d0.keys() != d1.keys():
        deld = set(d0.keys()) - set(d1.keys())
        addd = set(d1.keys()) - set(d0.keys())
        if deld:
            for k in sorted(deld):
                yield tabs + str(k) + " deleted"
        if addd:
            for k in sorted(addd):
                yield tabs + str(k) + " added"
    for k in sorted(set(d0.keys()).intersection(d1.keys())):
        if d0[k] != d1[k]:
            if isinstance(d0[k], dict) and isinstance(d1[k], dict):
                yield "{}{}:".format(tabs, k)
                yield from deepDictDiffIter(d0[k], d1[k], lvl+1)
            else:
                yield "{}{}: {} != {}".format(tabs, k, d0[k], d1[k])


class TestCase(unittest.TestCase):
    def assertDictEqual(self, d0, d1, msg=None):
        if d0 != d1:
            self.fail(self._formatMessage(
                msg,
                self._truncateMessage(
                    "Dicts not equal. Sizes {}, {}\n".format(
                        len(d0), len(d1)
                    ), "\n".join(deepDictDiffIter(d0, d1))
                )
            ))


class SimTest(TestCase):
    maxDiff = None
    def setUp(self):
        """Start an engine, install the sim module, and run it a while.

        This gives us some world-state to test upon.

        """
        from logging import getLogger, FileHandler
        self.engine = Engine(":memory:")
        logger = getLogger('LiSE.engine')
        logger.setLevel('DEBUG')
        logger.addHandler(FileHandler('test.log'))
        sim.install(self.engine)
        for i in range(72):
            self.engine.next_tick()
        self.engine.commit()

    def tearDown(self):
        """Close my engine."""
        self.engine.close()

    def testRulebooksCache(self):
        rulebooks = defaultdict(list)
        for (rulebook, rule) in self.engine.rule.query.rulebooks_rules():
            rulebooks[rulebook].append(rule)
        # Ignoring empty rulebooks because those only exist
        # implicitly, they don't have database records
        oldrulebooks = {}
        for (k, v) in self.engine._rulebooks_cache._data.items():
            if v:
                oldrulebooks[k] = [rule.name for rule in v]
        self.assertDictEqual(oldrulebooks, rulebooks)

    def testCharRulebooksCaches(self):
        charrb = {}
        for (
                character,
                character_rulebook,
                avatar_rulebook,
                character_thing_rulebook,
                character_place_rulebook,
                character_node_rulebook,
                character_portal_rulebook
        ) in self.engine.query.characters_rulebooks():
            charrb[character] = {
                'character': character_rulebook,
                'avatar': avatar_rulebook,
                'character_thing': character_thing_rulebook,
                'character_place': character_place_rulebook,
                'character_node': character_node_rulebook,
                'character_portal': character_portal_rulebook
            }
        self.assertDictEqual(
            charrb,
            self.engine._characters_rulebooks_cache._data
        )

    def testNodeRulebooksCache(self):
        noderb = defaultdict(dict)
        for (character, node, rulebook) in self.engine.query.nodes_rulebooks():
            noderb[character][node] = rulebook
        self.assertDictEqual(
            noderb,
            self.engine._nodes_rulebooks_cache._data
        )

    def testPortalRulebooksCache(self):
        portrb = StructuredDefaultDict(1, dict)
        for (character, nodeA, nodeB, rulebook) in self.engine.query.portals_rulebooks():
            portrb[character][nodeA][nodeB] = rulebook
        self.assertDictEqual(
            portrb,
            self.engine._portals_rulebooks_cache._data
        )

    def testAvatarnessCaches(self):
        user_avatarness = StructuredDefaultDict(3, WindowDict)
        for (character, graph, node, branch, tick, is_avatar) in self.engine.query.avatarness_dump():
            user_avatarness[graph][node][character][branch][tick] = is_avatar
        new_user_avatarness = StructuredDefaultDict(3, WindowDict)
        usr = self.engine._avatarness_cache.user_order
        for graph in usr:
            for node in usr[graph]:
                for char in usr[graph][node]:
                    if usr[graph][node][char]:
                        for branch in usr[graph][node][char]:
                            for tick, is_avatar in usr[graph][node][char][branch].items():
                                new_user_avatarness[graph][node][char][branch][tick] = is_avatar
        self.assertDictEqual(
            user_avatarness,
            new_user_avatarness
        )

    def testNodeRulesHandledCache(self):
        node_rules_handled_ticks = defaultdict(  # character:
            lambda: defaultdict(  # node:
                lambda: defaultdict(  # rulebook:
                    lambda: defaultdict(  # rule:
                        lambda: defaultdict(  # branch:
                            set  # ticks handled
                        )
                    )
                )
            )
        )
        new_node_rules_handled_ticks = defaultdict(  # character:
            lambda: defaultdict(  # node:
                lambda: defaultdict(  # rulebook:
                    lambda: defaultdict(  # rule:
                        dict
                    )
                )
            )
        )
        cache = self.engine._node_rules_handled_cache._data
        for char in cache:
            for node in cache[char]:
                for rulebook in cache[char][node]:
                    for rule in cache[char][node][rulebook]:
                        if cache[char][node][rulebook][rule]:
                            new_node_rules_handled_ticks[
                                char][node][rulebook][rule] \
                                = cache[char][node][rulebook][rule]
        for character, node, rulebook, rule, branch, tick in \
                self.engine.query.dump_node_rules_handled():
            node_rules_handled_ticks[
                character][node][rulebook][rule][branch].add(tick)
        self.assertDictEqual(
            node_rules_handled_ticks,
            new_node_rules_handled_ticks
        )

    def testPortalRulesHandledCache(self):
        portal_rules_handled_ticks = defaultdict(  # character:
            lambda: defaultdict(  # nodeA:
                lambda: defaultdict(  # nodeB:
                    lambda: defaultdict(  # rulebook:
                        lambda: defaultdict(  # rule:
                            lambda: defaultdict(  # branch:
                                set  # ticks handled
                            )
                        )
                    )
                )
            )
        )
        new_portal_rules_handled_ticks = defaultdict(  # character:
            lambda: defaultdict(  # nodeA:
                lambda: defaultdict(  # nodeB:
                    lambda: defaultdict(  # rulebook:
                        lambda: defaultdict(  # rule:
                            dict
                        )
                    )
                )
            )
        )
        cache = self.engine._portal_rules_handled_cache._data
        for character in cache:
            for nodeA in cache[character]:
                for nodeB in cache[character][nodeA]:
                    for rulebook in cache[character][nodeA][nodeB]:
                        for rule in cache[character][nodeA][nodeB][rulebook]:
                            if cache[character][nodeA][nodeB][rulebook][rule]:
                                new_portal_rules_handled_ticks[
                                    character][nodeA][nodeB][rulebook][rule] \
                                    = cache[character][nodeA][nodeB][
                                        rulebook][rule]
        for (character, nodeA, nodeB, idx, rulebook, rule, branch, tick) \
                in self.engine.query.dump_portal_rules_handled():
            portal_rules_handled_ticks[
                character][nodeA][nodeB][rulebook][rule][branch].add(tick)
        self.assertDictEqual(
            portal_rules_handled_ticks,
            new_portal_rules_handled_ticks
        )

    def testCharRulesHandledCaches(self):
        live = self.engine._character_rules_handled_cache._data
        for rulemap in [
                'character',
                'avatar',
                'character_thing',
                'character_place',
                'character_portal'
        ]:
            handled_ticks = StructuredDefaultDict(2, set)
            for character, rulebook, rule, branch, tick in getattr(
                    self.engine.query, 'handled_{}_rules'.format(rulemap)
            )():
                handled_ticks[character][rule][branch].add(tick)
            old_handled_ticks = StructuredDefaultDict(2, set)
            for character in live:
                if live[character][rulemap]:
                    for rule in live[character][rulemap]:
                        for branch, ticks in live[character][rulemap][rule].items():
                            self.assertIsInstance(ticks, set)
                            old_handled_ticks[character][rule][branch] = ticks
            self.assertDictEqual(
                old_handled_ticks,
                handled_ticks,
                "\n{} cache differs from DB".format(rulemap)
            )

    def testThingsCache(self):
        things = StructuredDefaultDict(3, tuple)
        for (character, thing, branch, tick, loc, nextloc) in \
                self.engine.query.things_dump():
            things[(character,)][thing][branch][tick] = (loc, nextloc)
        self.assertDictEqual(
            things,
            self.engine._things_cache.keys
        )

    def testRoommateCollisions(self):
        """Test queries' ability to tell that all of the students that share
        rooms have been in the same place.

        """
        done = set()
        for chara in self.engine.character.values():
            if chara.name in done:
                continue
            match = re.match('dorm(\d)room(\d)student(\d)', chara.name)
            if not match:
                continue
            dorm, room, student = match.groups()
            other_student = 1 if student == 0 else 0
            student = chara
            other_student = self.engine.character[
                'dorm{}room{}student{}'.format(dorm, room, other_student)
            ]
            
            same_loc_ticks = list(self.engine.ticks_when(
                student.avatar.only.historical('location')
                == other_student.avatar.only.historical('location')
            ))
            self.assertTrue(
                same_loc_ticks,
                "{} and {} don't seem to share a room".format(
                    student.name, other_student.name
                )
            )
            self.assertGreater(
                len(same_loc_ticks),
                6,
                "{} and {} share their room for less than 6 ticks".format(
                    student.name, other_student.name
                )
            )
            done.add(student.name)
            done.add(other_student.name)

    def testSoberCollisions(self):
        """Students that are neither lazy nor drunkards should all have been
        in class together at least once.

        """
        students = [
            stu for stu in
            self.engine.character['student_body'].stat['characters']
            if not (stu.stat['drunkard'] or stu.stat['lazy'])
        ]

        assert students

        def sameClasstime(stu0, stu1):
            self.assertTrue(
                self.engine.ticks_when(
                    stu0.avatar.only.historical('location') ==
                    stu1.avatar.only.historical('location') ==
                    self.engine.alias('classroom')
                ),
                "{stu0} seems not to have been in the classroom "
                "at the same time as {stu1}.\n"
                "{stu0} was there at ticks {ticks0}\n"
                "{stu1} was there at ticks {ticks1}".format(
                    stu0=stu0.name,
                    stu1=stu1.name,
                    ticks0=list(self.engine.ticks_when(stu0.avatar.only.historical('location') == self.engine.alias('classroom'))),
                    ticks1=list(self.engine.ticks_when(stu1.avatar.only.historical('location') == self.engine.alias('classroom')))
                )
            )
            return stu1

        reduce(sameClasstime, students)

    def testNoncollision(self):
        """Make sure students *not* from the same room never go there together"""
        dorm = defaultdict(lambda: defaultdict(dict))
        for character in self.engine.character.values():
            match = re.match('dorm(\d)room(\d)student(\d)', character.name)
            if not match:
                continue
            d, r, s = match.groups()
            dorm[d][r][s] = character
        for d in dorm:
            other_dorms = [dd for dd in dorm if dd != d]
            for r in dorm[d]:
                other_rooms = [rr for rr in dorm[d] if rr != r]
                for stu0 in dorm[d][r].values():
                    for rr in other_rooms:
                        for stu1 in dorm[d][rr].values():
                            self.assertFalse(
                                self.engine.ticks_when(
                                    stu0.avatar.only.historical('location') ==
                                    stu1.avatar.only.historical('location') ==
                                    self.engine.alias('dorm{}room{}'.format(d, r))
                                ),
                                "{} seems to share a room with {}".format(
                                    stu0.name, stu1.name
                                )
                            )
                    common = 'common{}'.format(d)
                    for dd in other_dorms:
                        for rr in dorm[dd]:
                            for stu1 in dorm[dd][rr].values():
                                self.assertFalse(
                                    self.engine.ticks_when(
                                        stu0.avatar.only.historical('location') ==
                                        stu1.avatar.only.historical('location') ==
                                        self.engine.alias(common)
                                    ),
                                    "{} seems to have been in the same"
                                    "common room  as {}".format(
                                        stu0.name, stu1.name
                                    )
                                )


if __name__ == '__main__':
    unittest.main()
