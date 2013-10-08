from django.utils import unittest
from taggit.models import Tag
from bluebottle.accounts.tests import UserTestsMixin
from apps.organizations.tests import OrganizationTestsMixin
from apps.projects.tests import ProjectTestsMixin


class TestTags(unittest.TestCase, ProjectTestsMixin, OrganizationTestsMixin, UserTestsMixin):
    """ Tests for tags. """

    def tearDown(self):
        # This shouldn't be necessary but the tests fail without it. There's
        # probably a bug somewhere but it's not worth tracking down right now.
        Tag.objects.all().delete()

    def test_tagging_multiple_models(self):
        """
        A smoke test to check that tagging is working how we want to use it.
        This is here because the Taggit tests don't all pass right now.
        """

        # Add the same tag to the 3 models we're currently tagging.
        tag_name = "Tag1"

        user = self.create_user()
        user.tags.add(tag_name)
        user.save()

        organization = self.create_organization()
        organization.save()

        organization.tags.add(tag_name)

        project = self.create_project()
        project.save()

        project.projectpitch.tags.add(tag_name)

        # Check that we only have one tag created.
        self.assertEquals(1, Tag.objects.count())

        # Check the tag name.
        tag = Tag.objects.all()[0]
        self.assertEquals(tag.name, tag_name)

        # Check that there are three objects tagged.
        num_tagged = len(tag.taggit_taggeditem_items.all())
        self.assertEquals(3, num_tagged)

    def test_same_tag_multiple_times(self):
        """
        A test to confirm that tagging an object with the same tag creates only
        one Tag.
        """

        tag_name = "Tag2"

        project = self.create_project()
        project.save()

        # Add the same tag two times.
        project.projectpitch.tags.add(tag_name)
        project.projectpitch.tags.add(tag_name)

        # Check that we only have one tag created.
        self.assertEquals(1, project.projectpitch.tags.count())
