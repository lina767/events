from rest_framework.test import APITestCase

from people.models import DuplicateCandidate, Person, PersonMergeLog
from people.tests.factories import make_person


class PersonApiTests(APITestCase):
    def test_create_person_with_emails(self):
        response = self.client.post(
            "/api/people/",
            {
                "display_name": "Jane Doe",
                "organization": "Acme Corp",
                "emails": ["jane@acme.example"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        person = Person.objects.get(person_id=response.data["person_id"])
        self.assertEqual(person.emails.get().email, "jane@acme.example")
        self.assertTrue(person.emails.get().is_primary)

    def test_creating_similar_person_surfaces_as_duplicate_candidate(self):
        make_person(display_name="Jane Doe")
        self.client.post("/api/people/", {"display_name": "Jane Doe"}, format="json")

        response = self.client.get("/api/duplicate-candidates/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_needs_review_lists_only_flagged_persons(self):
        make_person(display_name="Jane Doe", flagged_for_review=True)
        make_person(display_name="Robert Fischer", flagged_for_review=False)

        response = self.client.get("/api/people/needs-review/")
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["display_name"], "Jane Doe")

    def test_verify_clears_flag_and_stamps_timestamp(self):
        person = make_person(display_name="Jane Doe", flagged_for_review=True)

        response = self.client.post(f"/api/people/{person.person_id}/verify/")

        self.assertEqual(response.status_code, 200)
        person.refresh_from_db()
        self.assertFalse(person.flagged_for_review)
        self.assertIsNotNone(person.last_verified_at)

    def test_erase_endpoint_scrubs_and_logs(self):
        person = make_person(display_name="Jane Doe")

        response = self.client.post(
            f"/api/people/{person.person_id}/erase/",
            {"performed_by": "dpo@example.com", "reason": "GDPR request"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["is_deleted"])
        self.assertEqual(response.data["display_name"], "Deleted person")

        log_response = self.client.get("/api/deletion-logs/")
        self.assertEqual(log_response.data["count"], 1)

    def test_erase_endpoint_rejects_double_erasure(self):
        person = make_person(display_name="Jane Doe")
        self.client.post(
            f"/api/people/{person.person_id}/erase/", {"performed_by": "dpo@example.com"}, format="json"
        )

        response = self.client.post(
            f"/api/people/{person.person_id}/erase/", {"performed_by": "dpo@example.com"}, format="json"
        )

        self.assertEqual(response.status_code, 400)


class DuplicateCandidateApiTests(APITestCase):
    def _make_candidate(self):
        make_person(display_name="Jane Doe")
        make_person(display_name="Jane Doe")
        return DuplicateCandidate.objects.get()

    def test_confirm_merges_and_returns_confirmed_status(self):
        candidate = self._make_candidate()

        response = self.client.post(
            f"/api/duplicate-candidates/{candidate.id}/confirm/",
            {"keep": "a", "performed_by": "reviewer@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "confirmed")
        candidate.person_b.refresh_from_db()
        self.assertFalse(candidate.person_b.is_active)

    def test_reject_marks_as_not_a_duplicate(self):
        candidate = self._make_candidate()

        response = self.client.post(
            f"/api/duplicate-candidates/{candidate.id}/reject/",
            {"performed_by": "reviewer@example.com"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "rejected")

    def test_pending_list_excludes_decided_candidates(self):
        candidate = self._make_candidate()
        self.client.post(
            f"/api/duplicate-candidates/{candidate.id}/reject/",
            {"performed_by": "reviewer@example.com"},
            format="json",
        )

        response = self.client.get("/api/duplicate-candidates/")
        self.assertEqual(response.data["count"], 0)


class MergeLogApiTests(APITestCase):
    def test_revert_via_api(self):
        make_person(display_name="Jane Doe")
        make_person(display_name="Jane Doe")
        candidate = DuplicateCandidate.objects.get()
        self.client.post(
            f"/api/duplicate-candidates/{candidate.id}/confirm/",
            {"keep": "a", "performed_by": "reviewer@example.com"},
            format="json",
        )

        log = PersonMergeLog.objects.get()
        response = self.client.post(
            f"/api/merge-logs/{log.id}/revert/", {"performed_by": "reviewer@example.com"}
        )

        self.assertEqual(response.status_code, 200)
        candidate.person_b.refresh_from_db()
        self.assertTrue(candidate.person_b.is_active)
