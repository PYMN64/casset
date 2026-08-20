"""core/tests_seo.py — sitemaps, robots.txt, structured data and page titles.

These are the things that decide whether a Casset page is a rich result or
a bare blue link, and whether Google spends its crawl budget on tracks or
on infinite search-result permutations. They are also completely invisible
in normal use, which is exactly why they need tests.
"""

import json

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import UserProfile
from core.test_utils import make_publisher, make_user
from tracks.models import Album, Track


def _track(creator, **kwargs):
    defaults = {
        "title": "آهنگ تست",
        "content_type": Track.ContentType.MUSIC,
        "duration_seconds": 215,
        "status": Track.Status.APPROVED,
        "visibility": Track.Visibility.PUBLIC,
        "description": "توضیح کوتاه",
    }
    defaults.update(kwargs)
    return Track.objects.create(creator=creator, **defaults)


class RobotsTxtTests(TestCase):
    def test_served_as_plain_text(self):
        resp = self.client.get("/robots.txt")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp["Content-Type"].startswith("text/plain"))

    def test_disallows_private_and_infinite_routes(self):
        body = self.client.get("/robots.txt").content.decode()
        for path in ("/admin/", "/staff/", "/settings/", "/api/", "/search/", "/account/"):
            with self.subTest(path=path):
                self.assertIn(f"Disallow: {path}", body)

    @override_settings(ALLOWED_HOSTS=["casset.example"])
    def test_advertises_the_sitemap_on_the_live_host(self):
        """Hardcoding the host in a static file breaks the moment the site
        is served from staging, and a wrong sitemap URL is worse than none."""
        body = self.client.get("/robots.txt", SERVER_NAME="casset.example").content.decode()
        self.assertIn("Sitemap: http://casset.example/sitemap.xml", body)


class SitemapTests(TestCase):
    def setUp(self):
        self.creator = make_publisher("seo_creator", handle="seocreator")
        self.public = _track(self.creator, title="Public One")
        self.private = _track(self.creator, title="Private One",
                              visibility=Track.Visibility.PRIVATE)
        self.pending = _track(self.creator, title="Pending One",
                              status=Track.Status.SUBMITTED)

    def _body(self):
        resp = self.client.get("/sitemap.xml")
        self.assertEqual(resp.status_code, 200)
        return resp.content.decode()

    def test_lists_public_approved_tracks(self):
        self.assertIn(self.public.slug, self._body())

    def test_never_lists_private_or_unapproved_tracks(self):
        """A sitemap entry that 404s or redirects teaches Google to
        distrust the rest of our URLs."""
        body = self._body()
        self.assertNotIn(self.private.slug, body)
        self.assertNotIn(self.pending.slug, body)

    def test_lists_creators_with_a_public_handle(self):
        self.assertIn("/seocreator/", self._body())

    def test_never_lists_handle_less_accounts(self):
        """/@u-a1b2c3d4/ is an internal identifier, not a landing page."""
        plain = make_user("seo_plain")
        self.assertNotIn(plain.username, self._body())

    def test_public_album_listed_private_album_not(self):
        public_album = Album.objects.create(
            creator=self.creator, title="Public Album",
            content_type=Album.ContentType.MUSIC, is_public=True,
        )
        private_album = Album.objects.create(
            creator=self.creator, title="Private Album",
            content_type=Album.ContentType.MUSIC, is_public=False,
        )
        body = self._body()
        self.assertIn(f"/show/{public_album.id}/", body)
        self.assertNotIn(f"/show/{private_album.id}/", body)


class StructuredDataTests(TestCase):
    def setUp(self):
        self.creator = make_publisher("ld_creator", handle="ldcreator")

    def _jsonld(self, url):
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        start = html.index('<script type="application/ld+json">') + len('<script type="application/ld+json">')
        end = html.index("</script>", start)
        return json.loads(html[start:end])

    def test_music_track_uses_music_recording(self):
        track = _track(self.creator)
        data = self._jsonld(reverse("track_detail", args=[track.slug]))
        self.assertEqual(data["@type"], "MusicRecording")
        self.assertEqual(data["name"], track.title)
        self.assertEqual(data["byArtist"]["@type"], "Person")
        self.assertEqual(data["duration"], "PT3M35S")

    def test_podcast_track_uses_podcast_episode(self):
        """Marking a podcast up as a MusicRecording is worse than no
        markup — Google then distrusts the rest of the page too."""
        track = _track(self.creator, title="قسمت اول",
                       content_type=Track.ContentType.PODCAST)
        data = self._jsonld(reverse("track_detail", args=[track.slug]))
        self.assertEqual(data["@type"], "PodcastEpisode")
        self.assertIn("author", data)

    def test_private_track_never_advertises_a_media_url(self):
        """contentUrl on a non-public track would publish exactly what the
        visibility setting says not to."""
        track = _track(self.creator, title="Hidden", visibility=Track.Visibility.PRIVATE)
        self.client.login(username="ld_creator", password="pass12345")
        data = self._jsonld(reverse("track_detail", args=[track.slug]))
        self.assertNotIn("contentUrl", data)

    def test_profile_page_wraps_a_person(self):
        data = self._jsonld(f"/{self.creator.profile.public_handle}/")
        self.assertEqual(data["@type"], "ProfilePage")
        self.assertEqual(data["mainEntity"]["@type"], "Person")

    def test_script_breaking_title_cannot_escape_the_jsonld_block(self):
        """Stored XSS regression.

        json.dumps does not escape `<`, so a track titled
        `</script><img onerror=...>` used to close the ld+json element and
        execute on every page that rendered it. The JSON must round-trip
        intact while carrying no literal angle brackets.
        """
        track = _track(self.creator, title='</script><img src=x onerror=alert(1)>')
        resp = self.client.get(reverse("track_detail", args=[track.slug]))
        html = resp.content.decode()

        start = html.index('<script type="application/ld+json">') + len('<script type="application/ld+json">')
        end = html.index("</script>", start)
        block = html[start:end]

        # No literal angle bracket may survive into the script element —
        # one is all it takes to close it early.
        self.assertNotIn("<", block)
        self.assertNotIn(">", block)
        # ...and the title still decodes intact, so we escaped rather than
        # stripped: the markup is safe *and* the data is still correct.
        self.assertEqual(json.loads(block)["name"], track.title)

    def test_profile_lists_social_links_as_same_as(self):
        profile = self.creator.profile
        profile.instagram_url = "https://instagram.com/example"
        profile.website_url = "https://example.com"
        profile.save()
        data = self._jsonld(f"/{profile.public_handle}/")
        self.assertIn("https://instagram.com/example", data["mainEntity"]["sameAs"])


class PageTitleTests(TestCase):
    """Every page needs its own title. The old site shipped the literal
    string "Casset" on most of them, which is why none of them ranked."""

    def setUp(self):
        self.creator = make_publisher("title_creator", handle="titlecreator")
        self.track = _track(self.creator, title="آسمان ابری")
        make_user("title_user")

    def _title(self, url):
        html = self.client.get(url).content.decode()
        start = html.index("<title>") + len("<title>")
        return html[start:html.index("</title>", start)].strip()

    def test_public_pages_have_distinct_titles(self):
        titles = {
            "/discover/": self._title("/discover/"),
            "/trending/": self._title("/trending/"),
            "/search/": self._title("/search/"),
            "/login/": self._title("/login/"),
            "/register/": self._title("/register/"),
            "/terms/": self._title("/terms/"),
        }
        self.assertEqual(len(set(titles.values())), len(titles), titles)
        for url, title in titles.items():
            with self.subTest(url=url):
                self.assertNotEqual(title, "Casset")
                self.assertTrue(title)

    def test_track_title_names_the_track_and_creator(self):
        title = self._title(reverse("track_detail", args=[self.track.slug]))
        self.assertIn("آسمان ابری", title)
        self.assertIn(self.creator.profile.public_name(), title)

    def test_titles_stay_under_the_serp_cutoff(self):
        """Roughly 60 characters is what Google renders; longer titles get
        truncated mid-word."""
        for url in ("/discover/", "/trending/", "/login/", "/register/", "/search/"):
            with self.subTest(url=url):
                self.assertLessEqual(len(self._title(url)), 60)


class CanonicalTests(TestCase):
    def test_search_results_canonicalise_to_the_bare_page(self):
        """Search URLs are infinite and thin; consolidating them stops
        them competing with real content."""
        html = self.client.get("/search/?q=something").content.decode()
        self.assertIn('rel="canonical"', html)
        self.assertIn('href="http://testserver/search/"', html)


class OpenGraphImageTests(TestCase):
    def test_every_page_carries_an_og_image(self):
        """A link preview with no image reads as a broken link."""
        for url in ("/discover/", "/trending/", "/login/"):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), 'property="og:image"')


class ProfileUrlCanonicalisationTests(TestCase):
    def test_username_url_redirects_to_the_handle(self):
        """One person, one canonical profile URL — otherwise the two
        compete with each other in search."""
        creator = make_publisher("canon_creator", handle="canoncreator")
        resp = self.client.get(f"/@{creator.username}/")
        self.assertRedirects(resp, "/canoncreator/")

    def test_handle_less_profile_stays_on_the_username_url(self):
        user = make_user("canon_plain")
        resp = self.client.get(f"/@{user.username}/")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(UserProfile.objects.get(user=user).public_handle)
