import unittest

from _path import installPackagePath

installPackagePath()

from globalPlugins.whatsappWebPlusCompanion.cleanup import forceCloseOperation
from globalPlugins.whatsappWebPlusCompanion.models import Channel, LoaderError
from globalPlugins.whatsappWebPlusCompanion.packages import PackageInfo, PackageProcessCloseResult
from globalPlugins.whatsappWebPlusCompanion.security import SecurityProbe


SAFE_PROBE = SecurityProbe(True, False, False, False)


class CleanupTests(unittest.TestCase):
	def test_only_the_selected_channel_is_closed(self) -> None:
		closed = []

		def packageFinder(policy):
			return PackageInfo(policy.id.value, policy.packageFamily, f"C:\\{policy.id.value}")

		def processCloser(package):
			closed.append(package.fullName)
			return PackageProcessCloseResult(2, 0)

		result = forceCloseOperation(
			packageFinder=packageFinder,
			processCloser=processCloser,
			probeBuilder=lambda: SAFE_PROBE,
			channels=(Channel.BETA,),
		)
		self.assertEqual(closed, ["beta"])
		self.assertEqual((result.code, result.messageKey), ("processes.closed", "processes.closed.one"))
		self.assertEqual(result.values["channel"], "beta")
		none = forceCloseOperation(
			packageFinder=lambda policy: None,
			processCloser=processCloser,
			probeBuilder=lambda: SAFE_PROBE,
			channels=(Channel.STABLE,),
		)
		self.assertEqual((none.code, none.messageKey), ("processes.none", "processes.none.one"))

	def test_no_installed_or_running_packages_is_successful(self) -> None:
		result = forceCloseOperation(
			packageFinder=lambda policy: None,
			processCloser=lambda package: self.fail("No package should be closed"),
			probeBuilder=lambda: SAFE_PROBE,
		)
		self.assertTrue(result.ok)
		self.assertEqual(result.messageKey, "processes.none")

	def test_both_channels_are_closed_and_aggregated(self) -> None:
		def packageFinder(policy):
			return PackageInfo(policy.id.value, policy.packageFamily, f"C:\\{policy.id.value}")

		result = forceCloseOperation(
			packageFinder=packageFinder,
			processCloser=lambda package: PackageProcessCloseResult(2, 0),
			probeBuilder=lambda: SAFE_PROBE,
		)
		self.assertTrue(result.ok)
		self.assertEqual(result.messageKey, "processes.closed")
		self.assertEqual(result.values["closedCount"], 4)

	def test_partial_result_identifies_the_remaining_channel(self) -> None:
		def packageFinder(policy):
			return PackageInfo(policy.id.value, policy.packageFamily, f"C:\\{policy.id.value}")

		def processCloser(package):
			return PackageProcessCloseResult(2, 1 if package.fullName == Channel.BETA.value else 0)

		result = forceCloseOperation(
			packageFinder=packageFinder,
			processCloser=processCloser,
			probeBuilder=lambda: SAFE_PROBE,
		)
		self.assertFalse(result.ok)
		self.assertEqual(result.messageKey, "processes.partial")
		self.assertEqual(result.values["remainingChannels"], (Channel.BETA.value,))

	def test_discovery_failure_is_not_reported_as_no_processes(self) -> None:
		def packageFinder(policy):
			if policy.id == Channel.BETA:
				raise LoaderError("powershell.failed")
			return None

		result = forceCloseOperation(
			packageFinder=packageFinder,
			processCloser=lambda package: self.fail("No package should be closed"),
			probeBuilder=lambda: SAFE_PROBE,
		)
		self.assertFalse(result.ok)
		self.assertEqual(result.messageKey, "processes.failed")
		self.assertEqual(result.values["remainingChannels"], (Channel.BETA.value,))


if __name__ == "__main__":
	unittest.main()
