import io
import unittest
import zipfile

from inspect_embedded_python import scan_archive


def zipped(entries):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return stream.getvalue()


class ChaquopyImyScannerTest(unittest.TestCase):
    def test_scans_dist_info_nested_inside_imy(self):
        metadata = (
            "Metadata-Version: 2.1\n"
            "Name: certifi\n"
            "Version: 2026.11.18\n"
            "License-Expression: MPL-2.0\n"
        )
        imy = zipped({
            "certifi-2026.11.18.dist-info/METADATA": metadata,
            "certifi/__init__.py": "__version__ = '2026.11.18'\n",
        })
        aar = zipfile.ZipFile(io.BytesIO(zipped({
            "assets/chaquopy/requirements-common.imy": imy,
        })))
        packages, relevant, hints, scanned = [], [], {}, []

        scan_archive(aar, "wrapper.aar", packages, relevant, hints, archives_scanned=scanned)

        self.assertEqual(1, len(packages))
        self.assertEqual("certifi", packages[0]["name"])
        self.assertEqual("2026.11.18", packages[0]["version"])
        self.assertEqual("MPL-2.0", packages[0]["license"])
        self.assertIn("requirements-common.imy", scanned[1])
        self.assertEqual("2026.11.18", hints["certifi"])

    def test_scans_multiple_imy_archives_without_duplicate_records(self):
        metadata = "Name: yt-dlp\nVersion: 2026.11.17\nLicense: Unlicense\n"
        imy = zipped({"yt_dlp-2026.11.17.dist-info/METADATA": metadata})
        aar = zipfile.ZipFile(io.BytesIO(zipped({
            "assets/chaquopy/app.imy": imy,
            "assets/chaquopy/requirements-arm64-v8a.imy": imy,
        })))
        packages, relevant, hints, scanned = [], [], {}, []

        scan_archive(aar, "wrapper.aar", packages, relevant, hints, archives_scanned=scanned)

        self.assertEqual(2, len(packages))
        self.assertTrue(all(item["name"] == "yt-dlp" for item in packages))
        self.assertEqual(3, len(scanned))


if __name__ == "__main__":
    unittest.main()
