# -*- coding: utf-8 -*-
"""
Functional tests using Selenium.

See: ``docs/testing/selenium.rst`` for details.
"""
from random import randint
import time

from decimal import Decimal
from django.conf import settings
from django.utils.text import slugify
from django.utils.unittest.case import skipUnless

from apps.projects.models import Project
from .unittests import ProjectTestsMixin, UserTestsMixin

from bluebottle.tests.utils import SeleniumTestCase, css_dict


@skipUnless(getattr(settings, 'SELENIUM_TESTS', False),
        'Selenium tests disabled. Set SELENIUM_TESTS = True in your settings.py to enable.')
class DonationSeleniumTests(ProjectTestsMixin, UserTestsMixin, SeleniumTestCase):
    """
    Selenium tests for Projects.
    """

    fixtures = ['region_subregion_country_data.json'] # apps/geo/fixtures/

    def setUp(self):
        self.projects = dict([(slugify(title), title) for title in [
            u'Women first', u'Mobile payments for everyone!', u'Schools for children'
        ]])

        for slug, title in self.projects.items():
            project = self.create_project(title=title, slug=slug, money_asked=50000) # EUR 500.00

            project.projectcampaign.money_donated = 500 # EUR 5.00
            project.projectcampaign.save()
            project.phase = 'campaign'

        self.some_user = self.create_user()
        self.another_user = self.create_user()

        self.donate_details = {'firstname': 'Pietje',
                               'lastname': 'Paulusma',
                               'email': 'pietje@example.com',
                               'address': 'Herengracht 416',
                               'postcode': '1017BZ',
                               'city': 'Amsterdam',
                               'country': 'NL'}

    def visit_project_list_page(self, lang_code=None):
        self.visit_path('/projects', lang_code)

        self.assertTrue(self.browser.is_element_present_by_css('.item.item-project'),
                'Cannot load the project list page.')

    def test_view_project_page_with_donation(self):
        """
        Test project donation by an anonymous user
        """
        self.visit_project_list_page()

        # Besides the waiting for JS to kick in, we also need to wait for the funds raised animation to finish.
        time.sleep(2)

        # Click through to the project and verify we can support the project
        # and the fundraising values we expect

        self.browser.find_by_css('h3').first.click() # First project in the list
        self.assertTrue(self.browser.is_text_present('WOMEN FIRST',
                                                     wait_time=10))
        self.assertEqual(self.browser.find_by_css('h1.project-title').first.text, u'WOMEN FIRST')
        donation_status_text = self.browser.find_by_css('p.donate-amount').first.text
        self.assertTrue(u'5 OF' in donation_status_text and u'500 RAISED' in donation_status_text)
        self.assertTrue(u'SUPPORT PROJECT' in self.browser.find_by_css('div.donate-call-to-action').first.text)

        # Click through to the support-page, check the default values and
        # verify we are donating to the correct project 
        self.browser.find_by_css('div.donate-call-to-action a').first.click()

        self.assertTrue(self.browser.is_text_present('SUPPORT ONE OR MORE PROJECTS', wait_time=10))
        
        # TODO: Note that the browser back-button doesn't yet work from support-page back to project detail page

        self.assertEqual(self.browser.find_by_css('li.donation-project h2').first.text,
                         u'WOMEN FIRST\n,') # Required for country-label

        self.assertEqual(self.browser.find_by_css('.amount-control label').first.text,
                         u"I'D LIKE TO GIVE")
        self.assertTrue(u'495 IS STILL NEEDED' in self.browser.find_by_css('.amount-needed').first.text)
        input_field = self.browser.find_by_css('.amount-control input').first
        self.assertEqual(input_field['name'], u'donation-amount-1')
        self.assertEqual(input_field['value'], u'20')

        # Change the amount we want to donate

        # TODO: Verify we can change the amount to donate, this currently
        # doesn't work properly via Selenium: Doing the following gives me a 500:
        # TypeError: Cannot convert None to Decimal.

        # input_field.click()
        # input_field.fill(40)

        # TODO: Currently two donation-entries are added by default... I'm not sure why

        # Check the total and make sure there is only one donation entry
        # self.assertTrue(self.browser.find_by_css('.donation-total .currency').first.text.find(' 20') != -1)
        # self.assertTrue(len(self.browser.find_by_css('ul#donation-projects li.donation-project')) == 1)

        # Continue with our donation, fill in the details
        
        self.browser.find_by_css('.btn[href="#!/support/details"]').first.click()
        self.assertTrue(self.browser.is_text_present('Your full name',
                                                     wait_time=10))

        # NOTE: making use of fill_form_by_css() might be a better idea

        fields = self.browser.find_by_css('input[type=text]')
        firstname = fields[0]
        lastname = fields[1]
        email = fields[2]
        address = fields[3]
        postcode = fields[4]
        city = fields[5]
        
        self.assertEqual(firstname['placeholder'], u'First name')
        self.assertEqual(lastname['placeholder'], u'Last name')
        self.assertEqual(email['placeholder'], u'Email')
        self.assertEqual(address['placeholder'], u'Address')
        self.assertEqual(postcode['placeholder'], u'Postal code')
        self.assertEqual(city['placeholder'], u'City')

        firstname.fill(self.donate_details['firstname'])
        lastname.fill(self.donate_details['lastname'])
        email.fill(self.donate_details['email'])
        address.fill(self.donate_details['address'])
        postcode.fill(self.donate_details['postcode'])
        city.fill(self.donate_details['city'])

        # Click on the NEXT button
        self.browser.find_by_css('button.btn.right').first.click()
        time.sleep(2)
        # Don't sign up. Skip this form.
        self.browser.find_link_by_partial_text('Skip').first.click()

        self.assertTrue(self.browser.is_text_present("YOU'RE ALMOST THERE!", wait_time=10))
        
        # Proceed with the payment

        # self.browser.find_link_by_partial_text('Proceed').first.click()
        # self.assertTrue(self.browser.is_text_present('YOUR PAYMENT'))
        # self.assertTrue(self.browser.url.find('https://test.docdatapayments.com/') != -1)
        #
        # # Select Ideal + ING for payment
        #
        # self.browser.find_by_css('div.paymentChoiceMenuRow.ideal').first.click()
        # time.sleep(2)
        # self.browser.find_by_css("div.paymentChoiceMenuRow.ideal select.flowHorizontal").first.click()
        # time.sleep(2)
        # self.browser.find_by_css("div.paymentChoiceMenuRow.ideal option[value=ING]").first.click()
        # time.sleep(1)
        # self.browser.find_link_by_text('to iDEAL').first.click()
        #
        # time.sleep(2)
        #
        # self.assertTrue(self.browser.url.find('https://test.tripledeal.com/') != -1)
