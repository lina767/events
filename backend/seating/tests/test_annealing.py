from django.test import TestCase
from people.tests.factories import make_person

from seating.services.annealing import optimize
from seating.tests.factories import make_relationship, make_table


class OptimizeTests(TestCase):
    def test_respects_seat_pins(self):
        table_a = make_table(name="A", capacity=4)
        table_b = make_table(event=table_a.event, name="B", capacity=4)
        guests = [make_person() for _ in range(4)]

        from seating.models import SeatPin

        SeatPin.objects.create(event=table_a.event, person=guests[0], table=table_b)

        result = optimize(table_a.event, guests, iterations=200, seed=1)

        self.assertEqual(result["assignment"][guests[0].person_id], table_b.id)

    def test_never_exceeds_declared_capacity_meaningfully(self):
        table = make_table(capacity=2)
        guests = [make_person() for _ in range(2)]

        result = optimize(table.event, guests, iterations=100, seed=1)

        self.assertEqual(len(result["assignment"]), 2)
        for table_id in result["assignment"].values():
            self.assertEqual(table_id, table.id)

    def test_avoids_seating_hard_conflict_pairs_together_when_possible(self):
        table_a = make_table(name="A", capacity=2)
        table_b = make_table(event=table_a.event, name="B", capacity=2)
        a, b, c, d = [make_person() for _ in range(4)]
        make_relationship(a, b, edge_type="negative", is_hard_constraint=True)

        result = optimize(table_a.event, [a, b, c, d], iterations=1500, seed=7)

        self.assertNotEqual(result["assignment"][a.person_id], result["assignment"][b.person_id])

    def test_scope_table_ids_restricts_movement(self):
        table_a = make_table(name="A", capacity=4)
        table_b = make_table(event=table_a.event, name="B", capacity=4)
        guests = [make_person() for _ in range(4)]
        existing = {guests[0].person_id: table_b.id, guests[1].person_id: table_b.id}

        result = optimize(
            table_a.event,
            guests[:2],
            scope_table_ids={table_b.id},
            existing_assignment=existing,
            iterations=100,
            seed=1,
        )

        # Both guests started and stayed in the only table in scope.
        self.assertTrue(all(tid == table_b.id for tid in result["assignment"].values()))

    def test_explanations_are_provided_per_table(self):
        table = make_table(capacity=4)
        guests = [make_person(sector_tags=["tech"]), make_person(sector_tags=["finance"])]

        result = optimize(table.event, guests, iterations=50, seed=1)

        self.assertIn(table.id, result["explanations"])
        self.assertIsInstance(result["explanations"][table.id], str)
