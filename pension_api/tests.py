from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from pension_api.models import Nominee, NomineeVerification, User, Verification


class TestAdminApiSmoke(APITestCase):
    def setUp(self):
        self.user = User.objects.create(pension_id="P100", name="Alice", is_active=True, is_deceased=False)
        self.nominee = Nominee.objects.create(
            user=self.user, nominee_pension_id="N200", name="Bob", relation="Spouse", is_active=True
        )
        Verification.objects.create(user=self.user, status="success")
        NomineeVerification.objects.create(nominee=self.nominee, status="failure")

    def test_admin_user_detail_patch_without_file(self):
        url = reverse("user_detail", kwargs={"pension_id": self.user.pension_id})
        res = self.client.patch(url, {"name": "Alice Updated", "is_active": False}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["name"], "Alice Updated")
        self.assertEqual(res.data["is_active"], False)

    def test_admin_user_list_pagination(self):
        url = reverse("user_list")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("results", res.data)

    def test_admin_nominee_crud_without_file(self):
        list_url = reverse("admin_nominee_list_create")
        res = self.client.post(
            list_url,
            {"pension_id": self.user.pension_id, "nominee_pension_id": "N201", "name": "Cara", "relation": "Child"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        detail_url = reverse("admin_nominee_detail", kwargs={"nominee_pension_id": "N201"})
        res = self.client.patch(detail_url, {"relation": "Daughter"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["relation"], "Daughter")

        res = self.client.delete(detail_url)
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)

    def test_admin_nominee_get_by_id_and_put_replace(self):
        detail_url = reverse("admin_nominee_detail", kwargs={"nominee_pension_id": self.nominee.nominee_pension_id})

        get_res = self.client.get(detail_url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data["nominee_pension_id"], self.nominee.nominee_pension_id)

        put_res = self.client.put(
            detail_url,
            {
                "pension_id": self.user.pension_id,
                "nominee_pension_id": "N200-UPDATED",
                "name": "Bob Updated",
                "relation": "Brother",
                "is_active": False,
            },
            format="json",
        )
        self.assertEqual(put_res.status_code, status.HTTP_200_OK)
        self.assertEqual(put_res.data["nominee_pension_id"], "N200-UPDATED")
        self.assertEqual(put_res.data["name"], "Bob Updated")
        self.assertEqual(put_res.data["relation"], "Brother")
        self.assertEqual(put_res.data["is_active"], False)

    def test_admin_nominee_nested_parent_and_id_route(self):
        nested_url = reverse(
            "admin_nominee_detail_by_parent_id",
            kwargs={"pension_id": self.user.pension_id, "nominee_id": str(self.nominee.id)},
        )
        get_res = self.client.get(nested_url)
        self.assertEqual(get_res.status_code, status.HTTP_200_OK)
        self.assertEqual(get_res.data["id"], self.nominee.id)

        patch_res = self.client.patch(nested_url, {"relation": "Guardian"}, format="json")
        self.assertEqual(patch_res.status_code, status.HTTP_200_OK)
        self.assertEqual(patch_res.data["relation"], "Guardian")

    def test_admin_verification_history_endpoints(self):
        res = self.client.get(reverse("admin_verifications"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("results", res.data)

        res = self.client.get(reverse("admin_nominee_verifications"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("results", res.data)

    def test_admin_health_meta(self):
        res = self.client.get(reverse("admin_health"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], "ok")

        res = self.client.get(reverse("admin_meta"))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("docs", res.data)
