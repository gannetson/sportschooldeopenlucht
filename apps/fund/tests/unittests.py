import json
from apps.cowry.factory import _adapter_for_payment_method
from apps.cowry.models import PaymentStatuses
from apps.cowry_docdata.adapters import default_payment_methods
from apps.cowry_docdata.tests import run_docdata_tests
from django.test import TestCase
from django.test.client import Client
from django.utils import unittest
from django.utils import timezone
from django.test.utils import override_settings
from bluebottle.bluebottle_utils.tests import UserTestsMixin
from apps.projects.tests import ProjectTestsMixin
from apps.projects.models import Project
from rest_framework import status
from ..models import Order, OrderStatuses, DonationStatuses, RecurringDirectDebitPayment


class CartApiIntegrationTest(ProjectTestsMixin, UserTestsMixin, TestCase):
    """
    Integration tests for the adding Donations to an Order (a cart in this case).
    """
    def setUp(self):
        self.some_project = self.create_project(money_asked=50000)
        self.another_project = self.create_project(money_asked=75000)

        self.some_user = self.create_user()
        self.another_user = self.create_user()

        self.current_donations_url = '/api/fund/orders/current/donations/'
        self.current_order_url = '/api/fund/orders/current'
        self.payment_profile_current_url = '/api/fund/paymentprofiles/current'
        self.payment_url_base = '/api/fund/payments/'
        self.order_url_base = '/api/fund/orders/'

        self.some_profile = {'first_name': 'Nijntje',
                             'last_name': 'het Konijnje',
                             'email': 'nijntje@hetkonijnje.nl',
                             'address': 'Dam',
                             'postal_code': '1001AM',
                             'city': 'Amsterdam',
                             'country': 'NL'}

    def test_current_order_donation_crud(self):
        """
        Tests for creating, retrieving, updating and deleting a donation to shopping cart.
        """
        # First make sure we have a current order
        self.client.login(username=self.some_user.email, password='password')
        response = self.client.get(self.current_order_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['status'], 'current')

        # Create a Donation
        response = self.client.post(self.current_donations_url, {'project': self.some_project.slug, 'amount': 35})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['amount'], '35.00')
        self.assertEqual(response.data['project'], self.some_project.slug)
        self.assertEqual(response.data['status'], 'new')

        # Retrieve the created Donation
        donation_detail_url = "{0}{1}".format(self.current_donations_url, response.data['id'])
        response = self.client.get(donation_detail_url)
        self.assertEqual(response.data['amount'], '35.00')
        self.assertEqual(response.data['project'], self.some_project.slug)

        # Retrieve the list with all donations in this cart should return one
        response = self.client.get(self.current_donations_url)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['amount'], '35.00')
        self.assertEqual(response.data['results'][0]['project'], self.some_project.slug)

        # Create another Donation
        response = self.client.post(self.current_donations_url,
                                    {'project': self.another_project.slug, 'amount': '12.50'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['amount'], '12.50')
        self.assertEqual(response.data['project'], self.another_project.slug)

        # Create a Donation under 5 should fail
        response = self.client.post(self.current_donations_url,
                                    {'project': self.another_project.slug, 'amount': '2.50'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

        # Retrieve the list with all donations in this cart should return one
        response = self.client.get(self.current_donations_url)
        self.assertEqual(response.data['count'], 2)
        self.assertEqual(response.data['results'][0]['amount'], '35.00')
        self.assertEqual(response.data['results'][1]['amount'], '12.50')
        self.assertEqual(response.data['results'][0]['project'], self.some_project.slug)

        # Update the created Donation by owner.
        response = self.client.put(donation_detail_url, json.dumps({'amount': 150, 'project': self.some_project.slug}), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['amount'], '150.00')

        # Update with amount under 5 should fail.
        response = self.client.put(donation_detail_url, json.dumps({'amount': 3, 'project': self.some_project.slug}), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

        # Update the status of the created Donation by owner should be ignored
        response = self.client.put(donation_detail_url,json.dumps({'amount': 150, 'project': self.some_project.slug, 'status': 'paid'}), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['amount'], '150.00')
        self.assertEqual(response.data['status'], 'new')

        # Delete a donation should work the list should have one donation now
        response = self.client.delete(donation_detail_url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT, response.data)
        response = self.client.get(self.current_donations_url)
        self.assertEqual(response.data['count'], 1)

        # Another user should not see the cart of the first user
        self.client.logout()
        self.client.login(username=self.another_user.email, password='password')
        # make a cart for this another user
        self.client.get(self.current_order_url)
        response = self.client.get(self.current_donations_url)
        self.assertEqual(response.data['count'], 0)

        # Another user should not be able to view a donation in the cart of the first user
        response = self.client.get(donation_detail_url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND, response.data)

        # Now let's get anonymous and create a donation
        self.client.logout()
        # make a cart for this anonymous user
        self.client.get(self.current_order_url)
        response = self.client.post(self.current_donations_url, {'project': self.some_project.slug, 'amount': 71})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['amount'], '71.00')
        self.assertEqual(response.data['project'], self.some_project.slug)
        self.assertEqual(response.data['status'], 'new')
        response = self.client.get(self.current_donations_url)
        self.assertEqual(response.data['count'], 1)

        # Login as the first user and cart should only have the one donation from  the anonymous cart.
        self.client.login(username=self.some_user.email, password='password')
        response = self.client.get(self.current_donations_url)
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['amount'], '71.00')
        self.assertEqual(response.data['results'][0]['project'], self.some_project.slug)

        # Log out again... The anonymous cart should NOT be returned
        self.client.logout()
        self.client.get(self.current_order_url)
        response = self.client.get(self.current_donations_url)
        self.assertEqual(response.data['count'], 0)

    def test_current_order_monthly(self):
        # Test setting a recurring order as logged in user.
        self.client.login(username=self.some_user.email, password='password')
        response = self.client.get(self.current_order_url)
        self.assertEqual(response.data['recurring'], False)
        response = self.client.put(self.current_order_url, json.dumps({'recurring': True}), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['recurring'], True)

        # Test that setting a recurring order as anonymous user fails.
        self.client.logout()
        response = self.client.get(self.current_order_url)
        self.assertEqual(response.data['recurring'], False)
        response = self.client.put(self.current_order_url, json.dumps({'recurring': True}), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        response = self.client.get(self.current_order_url)
        self.assertEqual(response.data['recurring'], False)

    @override_settings(COWRY_PAYMENT_METHODS=default_payment_methods)
    @unittest.skipUnless(run_docdata_tests, 'DocData credentials not set or not online')
    def test_payment_profile_and_payment_api(self):
        """
        Integration tests for the PaymentProfile and Payment APIs.
        """
        # Setup.
        self._make_api_donation(self.some_user, amount=35, set_payment_method=False)
        payment_url = '{0}{1}'.format(self.payment_url_base, 'current')
        response = self.client.get(payment_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        first_payment_method = response.data['available_payment_methods'][0]

        # Updating the payment method with a value not in the available list should fail.
        response = self.client.put(payment_url, json.dumps({'payment_method': 'some-new-fancy-pm'}), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

        # Updating the payment method with a valid value should provide a payment_url.
        response = self.client.put(payment_url, json.dumps({'payment_method': first_payment_method}), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertTrue(response.data['payment_url'])  # Not empty payment_url.

        # Emulate a status change from DocData. Note we need to use an internal API from COWRY for this but it's hard
        # to avoid because we can't automatically make a DocData payment.
        order = Order.objects.get(user=self.some_user)
        adapter = _adapter_for_payment_method(order.latest_payment.payment_method_id)
        adapter._change_status(order.latest_payment, PaymentStatuses.pending)
        order = Order.objects.get(id=order.id)
        self.assertEqual(order.status, OrderStatuses.closed)

    @override_settings(COWRY_PAYMENT_METHODS=default_payment_methods)
    @unittest.skipUnless(run_docdata_tests, 'DocData credentials not set or not online')
    def test_donation_status_changes(self):
        self.assertEqual(self.some_project.projectcampaign.money_needed, 50000)
        self.assertEqual(self.some_project.phase, 'campaign')

        self._make_api_donation(self.some_user, project=self.some_project, amount=350)
        # Reload the project from db adn check phase / money_needed
        project = Project.objects.get(pk=self.some_project.id)
        self.assertEqual(project.phase, 'campaign')
        self.assertEqual(project.projectcampaign.money_needed, 15000)

        self._make_api_donation(self.another_user, project=self.some_project, amount=150)
        # Reload the project from db and check phase / money_needed
        project = Project.objects.get(pk=self.some_project.id)
        self.assertEqual(project.phase, 'act')
        self.assertEqual(project.projectcampaign.money_needed, 0)

    @override_settings(COWRY_PAYMENT_METHODS=default_payment_methods)
    @unittest.skipUnless(run_docdata_tests, 'DocData credentials not set or not online')
    def test_payment_permissions(self):
        # 'some_user' should be able to access their payment.
        order_id = self._make_api_donation(self.some_user, project=self.some_project, amount=50)
        response = self.client.get('{0}{1}'.format(self.order_url_base, order_id))
        some_user_payment_url = '{0}{1}'.format(self.payment_url_base, response.data['payments'][0])
        response = self.client.get(some_user_payment_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.client.logout()

        # 'another_user' should be able to access their payment.
        order_id = self._make_api_donation(self.another_user, project=self.some_project, amount=100)
        response = self.client.get('{0}{1}'.format(self.order_url_base, order_id))
        another_user_payment_url = '{0}{1}'.format(self.payment_url_base, response.data['payments'][0])
        response = self.client.get(another_user_payment_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        # 'another_user' should not be able to access the payment belonging to 'some_user'.
        response = self.client.get(some_user_payment_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)
        self.client.logout()

        # Anonymous user shouldn't be able to access the payments from 'some_user' and 'another_user'.
        response = self.client.get(some_user_payment_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)
        response = self.client.get(another_user_payment_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)

        # Anonymous user 1 should be able to access their payment.
        order_id = self._make_api_donation(None, project=self.some_project, amount=150)  # Anonymous donation.
        response = self.client.get('{0}{1}'.format(self.order_url_base, order_id))
        anonymous_payment_url_1 = '{0}{1}'.format(self.payment_url_base, response.data['payments'][0])
        response = self.client.get(anonymous_payment_url_1)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        # Anonymous user 2 (from a second client) should be able to access their payment as well.
        secondClient = Client()
        order_id = self._make_api_donation(None, project=self.some_project, amount=150, client=secondClient)  # Anonymous donation.
        response = secondClient.get('{0}{1}'.format(self.order_url_base, order_id))
        anonymous_payment_url_2 = '{0}{1}'.format(self.payment_url_base, response.data['payments'][0])
        response = secondClient.get(anonymous_payment_url_2)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        # Anonymous user 1 should not be able to access the payment from anonymous user 2.
        response = self.client.get(anonymous_payment_url_2)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)

        # Anonymous user 2 should not be able to access the payment from anonymous user 1.
        response = secondClient.get(anonymous_payment_url_1)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)

    @override_settings(COWRY_PAYMENT_METHODS=default_payment_methods)
    @unittest.skipUnless(run_docdata_tests, 'DocData credentials not set or not online')
    def test_order_permissions(self):
        # Note: This method is very similar to test_payment_permissions but
        # it's required to test the IsOrderCreator permission class.

        # 'some_user' should be able to access their order.
        order_id = self._make_api_donation(self.some_user, project=self.some_project, amount=50)
        response = self.client.get('{0}{1}'.format(self.order_url_base, order_id))
        some_user_order_url = '{0}{1}'.format(self.order_url_base, response.data['id'])
        response = self.client.get(some_user_order_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.client.logout()

        # 'another_user' should be able to access their order.
        order_id = self._make_api_donation(self.another_user, project=self.some_project, amount=100)
        response = self.client.get('{0}{1}'.format(self.order_url_base, order_id))
        another_user_order_url = '{0}{1}'.format(self.order_url_base, response.data['id'])
        response = self.client.get(another_user_order_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        # 'another_user' should not be able to access the order belonging to 'some_user'.
        response = self.client.get(some_user_order_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)
        self.client.logout()

        # Anonymous user shouldn't be able to access the orders from 'some_user' and 'another_user'.
        response = self.client.get(some_user_order_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)
        response = self.client.get(another_user_order_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)

        # Anonymous user 1 should be able to access their order.
        order_id = self._make_api_donation(None, project=self.some_project, amount=150)  # Anonymous donation.
        response = self.client.get('{0}{1}'.format(self.order_url_base, order_id))
        anonymous_order_url_1 = '{0}{1}'.format(self.order_url_base, response.data['id'])
        response = self.client.get(anonymous_order_url_1)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        # Anonymous user 2 (from a second client) should be able to access their order as well.
        secondClient = Client()
        order_id = self._make_api_donation(None, project=self.some_project, amount=150, client=secondClient)  # Anonymous donation.
        response = secondClient.get('{0}{1}'.format(self.order_url_base, order_id))
        anonymous_order_url_2 = '{0}{1}'.format(self.order_url_base, response.data['id'])
        response = secondClient.get(anonymous_order_url_2)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        # Anonymous user 1 should not be able to access the order from anonymous user 2.
        response = self.client.get(anonymous_order_url_2)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)

        # Anonymous user 2 should not be able to access the payment from anonymous user 1.
        response = secondClient.get(anonymous_order_url_1)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)

    @override_settings(COWRY_PAYMENT_METHODS=default_payment_methods)
    @unittest.skipUnless(run_docdata_tests, 'DocData credentials not set or not online')
    def test_order_closed_api(self):
        # Setup.
        order_id = self._make_api_donation(self.some_user, project=self.some_project, amount=10)
        # Emulate a status change from DocData. Note we need to use an internal API from COWRY for this but it's hard
        # to avoid because we can't automatically make a DocData payment.
        order = Order.objects.get(id=order_id)
        adapter = _adapter_for_payment_method(order.latest_payment.payment_method_id)
        adapter._change_status(order.latest_payment, PaymentStatuses.pending)
        order = Order.objects.get(id=order.id)
        self.assertEqual(order.status, OrderStatuses.closed)

        # Editing the recurring status of a closed order should not be allow.
        order_detail_url = '{0}{1}'.format(self.order_url_base, order_id)
        response = self.client.put(order_detail_url, json.dumps({'recurring': True}), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        # Listing a closed order should be allowed.
        order_donation_list_url = '{0}{1}'.format(order_detail_url, '/donations/')
        response = self.client.get(order_donation_list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response.data), 1)

        # Editing a donation with order closed should not be allowed.
        donation_detail_url = '{0}{1}'.format(order_donation_list_url, response.data[0]['id'])
        response = self.client.put(donation_detail_url, json.dumps({'project': self.some_project.slug, 'amount': 5}), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)

        # Adding a donation to a closed order should not be allowed.
        response = self.client.post(order_donation_list_url, {'project': self.some_project.slug, 'amount': 10})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, response.data)

    @override_settings(COWRY_PAYMENT_METHODS=default_payment_methods)
    @unittest.skipUnless(run_docdata_tests, 'DocData credentials not set or not online')
    def test_payment_flow_with_payment_cancel(self):

        # Setup.
        first_donation_amount = 20
        second_donation_amount = 10
        order_id = self._make_api_donation(self.some_user, amount=first_donation_amount)
        order = Order.objects.get(id=order_id)
        first_payment = order.latest_payment
        self.assertEqual(first_payment.status, PaymentStatuses.in_progress)
        self.assertEqual(first_payment.amount, order.total)

        # Get the 'current' Order again. This should cancel the 'current' payment.
        response = self.client.get(self.current_order_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        second_payment = order.latest_payment
        self.assertNotEqual(first_payment.id, second_payment.id)  # Ensure we have a new payment.
        self.assertEqual(second_payment.status, PaymentStatuses.new)  # Ensure the payment is in status new.

        # Adding a donation to the order should update the payment.
        response = self.client.post(self.current_donations_url, {'project': self.some_project.slug, 'amount': second_donation_amount})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        # order = Order.objects.get(id=order_id)
        new_order_total = (first_donation_amount + second_donation_amount) * 100
        self.assertEqual(order.total, new_order_total)

        # Update the payment.
        payment_url = '{0}{1}'.format(self.payment_url_base, 'current')
        response = self.client.get(payment_url)
        self.assertFalse(response.data['payment_url'])  # Empty payment_url.
        self.assertTrue(response.data['available_payment_methods'])

        # Check the the payment total is correct.
        self.assertEqual(order.latest_payment.id, second_payment.id)  # Ensure we don't have a new payment.
        self.assertEqual(order.latest_payment.amount, new_order_total)

    def _format_donation(self, amount):
        """ Helper method to format donations as they are formatted in the API. """
        return '{0}.{1}'.format(str(amount*100)[:-2], str(amount*100)[-2:])

    def _make_api_donation(self, user, project=None, amount=20, payment_profile=None, client=None, set_payment_method=True):
        """
        Helper method for making a donation with the api. This creates a donation and tests the full order cycle
        until the URL is generated.
        """
        if not project:
            project = self.some_project

        if not payment_profile:
            payment_profile = self.some_profile

        if not client:
            client = self.client

        # Make sure we have a current order. The donation will be anonymous if no user is supplied.
        if user:
            client.login(username=user.email, password='password')
        response = client.get(self.current_order_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['status'], 'current')
        order_id = response.data['id']

        # Create a Donation for the current order.
        response = client.post(self.current_donations_url, {'project': project.slug, 'amount': amount})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data['amount'], self._format_donation(amount))
        self.assertEqual(response.data['project'], project.slug)
        self.assertEqual(response.data['status'], 'new')

        # Now retrieve the current order payment profile.
        response = client.get(self.payment_profile_current_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)

        # Update the current order payment profile with our information.
        response = client.put(self.payment_profile_current_url, json.dumps(payment_profile), 'application/json')
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data['first_name'], payment_profile['first_name'])
        self.assertEqual(response.data['last_name'], payment_profile['last_name'])
        self.assertEqual(response.data['email'], payment_profile['email'])
        self.assertEqual(response.data['address'], payment_profile['address'])
        self.assertEqual(response.data['postal_code'], payment_profile['postal_code'])
        self.assertEqual(response.data['city'], payment_profile['city'])
        self.assertEqual(response.data['country'], payment_profile['country'])

        # Now it's time to pay. Get the order so that we can get the payment.
        response = client.get(self.current_order_url)
        formatted_amount = self._format_donation(amount)
        self.assertEqual(response.data['total'], formatted_amount)
        self.assertTrue(response.data['payments'])

        # Get the payment.
        payment_url = '{0}{1}'.format(self.payment_url_base, 'current')
        response = client.get(payment_url)
        self.assertFalse(response.data['payment_url'])  # Empty payment_url.
        self.assertTrue(response.data['available_payment_methods'])
        first_payment_method = response.data['available_payment_methods'][0]

        # Updating the payment method with a valid value should provide a payment_url.
        if set_payment_method:
            response = client.put(payment_url, json.dumps({'payment_method': first_payment_method}), 'application/json')
            self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
            self.assertTrue(response.data['payment_url'].startswith('http'))

        # Now let's make sure the donations in this order change to pending.
        order = Order.objects.get(pk=order_id)
        for donation in order.donations:
            donation.status = DonationStatuses.pending
            donation.save()

        return order_id


# Voucher code is disabled for now.
# class VoucherApiIntegrationTest(ProjectTestsMixin, TestCase):
#     """
#     Integration tests for the adding Donations to an Order (a cart in this case)
#     """
#     def setUp(self):
#         self.some_project = self.create_project()
#         self.another_project = self.create_project()
#         self.some_user = self.create_user()
#         self.another_user = self.create_user()
#         self.current_vouchers_url = '/api/fund/orders/current/vouchers/'
#         self.vouchers_url = '/api/fund/vouchers/'
#         self.current_order_url = '/api/fund/orders/current'
#         self.some_voucher_data = {
#             'amount': 25, 'text': 'Look at this!',
#             'receiver_name': 'Bart', 'receiver_email': 'bart@1procentclub.nl',
#             'sender_name': 'Webmaster', 'sender_email': 'webmaster@1procentclub.nl'
#         }
#         self.another_voucher_data = {
#             'amount': 50, 'receiver_email': 'you@1procentclub.nl', 'sender_email': 'me@1procentclub.nl'
#         }
#
#     def test_current_order_voucher_crud(self):
#         """
#         Tests for creating, retrieving, updating and deleting a voucher to shopping cart.
#         """
#         # First make sure we have a current order
#         self.client.login(username=self.some_user.email, password='password')
#         response = self.client.get(self.current_order_url)
#         self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
#         self.assertEqual(response.data['status'], 'current')
#
#         # Create a Voucher.
#         response = self.client.post(self.current_vouchers_url, self.some_voucher_data)
#         some_voucher_detail_url = '{0}{1}'.format(self.current_vouchers_url, response.data['id'])
#         self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
#         self.assertEqual(response.data['amount'], '25.00')
#         self.assertEqual(response.data['receiver_name'], self.some_voucher_data['receiver_name'])
#         self.assertEqual(response.data['status'], 'new')
#
#         # Create another voucher.
#         response = self.client.post(self.current_vouchers_url, self.another_voucher_data)
#         another_voucher_detail_url = '{0}{1}'.format(self.current_vouchers_url, response.data['id'])
#         self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
#         self.assertEqual(response.data['amount'], '50.00')
#         self.assertEqual(response.data['receiver_email'], self.another_voucher_data['receiver_email'])
#         self.assertEqual(response.data['status'], 'new')
#
#         # Check that the order now holds that two vouchers.
#         response = self.client.get(self.current_order_url)
#         self.assertEqual(response.data['total'], '75.00')
#         response = self.client.get(self.current_vouchers_url)
#         self.assertEqual(len(response.data['results']), 2)
#
#         # Remove the first voucher and see if all is updated correctly.
#         response = self.client.delete(some_voucher_detail_url)
#         self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
#         response = self.client.get(self.current_order_url)
#         self.assertEqual(response.data['total'], '50.00')
#         response = self.client.get(self.current_vouchers_url)
#         self.assertEqual(len(response.data['results']), 1)
#
#         # Setting 77 as amount should fail
#         self.some_voucher_data['amount'] = 77
#         response = self.client.post(self.current_vouchers_url, self.some_voucher_data)
#         self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)
#
#         # Sending a status should not be saved
#         self.some_voucher_data['amount'] = 10
#         self.some_voucher_data['status'] = 'paid'
#         response = self.client.post(self.current_vouchers_url, self.some_voucher_data)
#         self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
#         self.assertEqual(response.data['amount'], '10.00')
#         self.assertEqual(response.data['receiver_email'], self.some_voucher_data['receiver_email'])
#         self.assertEqual(response.data['status'], 'new')
#
#         # Updating the amount on a voucher is fine
#         self.another_voucher_data['amount'] = 100
#         response = self.client.put(another_voucher_detail_url, json.dumps(self.another_voucher_data), 'application/json')
#         self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
#         self.assertEqual(response.data['amount'], '100.00')
#
#         self.some_voucher_data['receiver_email'] = 'not good'
#         self.some_voucher_data['sender_email'] = None
#         response = self.client.post(self.current_vouchers_url, self.some_voucher_data)
#         self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST, response.data)


class RecurringPaymentTest(UserTestsMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()

    def test_post_save_disabled(self):
        recurring_payment = RecurringDirectDebitPayment(user=self.user, active=True, name="ABC", city="DEF", account=123)
        recurring_payment.save()

        self.assertTrue(recurring_payment.active)
        self.user.deleted = timezone.now()
        self.user.save()
        recurring_payment = RecurringDirectDebitPayment.objects.get(user=self.user)
        self.assertFalse(recurring_payment.active)

    def test_post_delete_removed(self):
        recurring_payment = RecurringDirectDebitPayment(user=self.user, active=True, name="GHI", city="JKL", account=456)
        recurring_payment.save()

        self.assertTrue(recurring_payment.active)
        self.user.delete()
        recurring_payment = RecurringDirectDebitPayment.objects.filter(user=self.user)
        self.assertEqual(len(recurring_payment), 0)