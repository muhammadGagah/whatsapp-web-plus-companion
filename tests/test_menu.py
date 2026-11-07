import importlib
import pathlib
import sys
import types
import unittest
from unittest import mock

from _path import installPackagePath

installPackagePath()


class FakeMenuItem:
	_nextId = 1

	def __init__(self, label: str) -> None:
		self.Id = self._nextId
		FakeMenuItem._nextId += 1
		self.label = label
		self.destroyed = False

	def Enable(self, enabled) -> None:
		self.enabled = enabled

	def Check(self, checked) -> None:
		self.checked = checked

	def Destroy(self) -> None:
		self.destroyed = True


class FakeMenu:
	def __init__(self) -> None:
		self.entries: list[FakeMenuItem | None] = []
		self.removed: list[int] = []
		self.destroyed = False

	def Append(self, itemId, label: str, helpText: str) -> FakeMenuItem:
		item = FakeMenuItem(label)
		self.entries.append(item)
		return item

	def AppendCheckItem(self, itemId, label: str, helpText: str) -> FakeMenuItem:
		item = self.Append(itemId, label, helpText)
		item.checkable = True
		return item

	def AppendSeparator(self) -> None:
		self.entries.append(None)

	def Remove(self, itemId: int) -> None:
		self.removed.append(itemId)

	def Destroy(self) -> None:
		self.destroyed = True


class FakeToolsMenu(FakeMenu):
	def AppendSubMenu(self, menu: FakeMenu, label: str, helpText: str) -> FakeMenuItem:
		item = FakeMenuItem(label)
		self.entries.append(item)
		return item


class FakeOwner:
	def __init__(self) -> None:
		self.toolsMenu = FakeToolsMenu()
		self.bound: list[tuple[object, object]] = []
		self.unbound: list[tuple[object, object]] = []

	def Bind(self, eventType, handler, item=None) -> None:
		self.bound.append((handler, item))

	def Unbind(self, eventType, *, handler, source=None) -> None:
		self.unbound.append((handler, source))


class MenuTests(unittest.TestCase):
	def setUp(self) -> None:
		self.owner = FakeOwner()
		fakeWx = types.SimpleNamespace(
			Menu=FakeMenu,
			MenuItem=FakeMenuItem,
			CommandEvent=object,
			EVT_MENU=object(),
			EVT_UPDATE_UI=object(),
			EVT_MENU_OPEN=object(),
			EVT_MENU_CLOSE=object(),
			ID_ANY=-1,
		)
		fakeGui = types.SimpleNamespace(mainFrame=types.SimpleNamespace(sysTrayIcon=self.owner))
		with mock.patch.dict(sys.modules, {"wx": fakeWx, "gui": fakeGui}):
			sys.modules.pop("globalPlugins.whatsappWebPlusCompanion.menu", None)
			self.menuModule = importlib.import_module("globalPlugins.whatsappWebPlusCompanion.menu")

	def test_native_submenu_binds_every_item_and_cleans_up(self) -> None:
		handlers = [lambda event: None for _ in range(3)]
		sections = (
			(
				self.menuModule.MenuSpec("One", "First", handlers[0]),
				self.menuModule.MenuSpec("Two", "Second", handlers[1]),
			),
			(self.menuModule.MenuSpec("Three", "Third", handlers[2]),),
		)
		menu = self.menuModule.CompanionMenu("Companion", "Help", sections)
		self.assertEqual(len(self.owner.bound), 3)
		self.assertEqual(
			[entry.label if entry else None for entry in menu._menu.entries],
			["One", "Two", None, "Three"],
		)
		parentItem = menu._parentItem
		childItems = [item for item, handler in menu._bindings]

		menu.terminate()

		self.assertEqual(len(self.owner.unbound), 3)
		self.assertTrue(all(item.destroyed for item in childItems))
		self.assertTrue(parentItem.destroyed)
		self.assertTrue(menu._menu.destroyed)
		self.assertIn(parentItem.Id, self.owner.toolsMenu.removed)

	def test_start_and_stop_have_independent_native_enabled_states(self) -> None:
		state = {"call": False, "recording": False}
		menu = self.menuModule.CompanionMenu(
			"Companion",
			"Help",
			(
				(
					self.menuModule.MenuSpec("Start", "", lambda event: None, lambda: state["call"]),
					self.menuModule.MenuSpec("Stop", "", lambda event: None, lambda: state["recording"]),
				),
			),
		)
		start, stop = menu._menu.entries
		self.assertFalse(start.enabled)
		self.assertFalse(stop.enabled)
		state["call"] = True
		menu.refreshEnabled()
		self.assertTrue(start.enabled)
		state.update(call=False, recording=True)
		menu.refreshEnabled()
		self.assertFalse(start.enabled)
		self.assertTrue(stop.enabled)
		menu.terminate()
		self.assertEqual(len(self.owner.bound), len(self.owner.unbound))

	def test_open_menu_refreshes_until_any_menu_closes(self) -> None:
		timers = []

		class Timer:
			def __init__(self, delay, function) -> None:
				self.function = function
				self.stopped = False
				timers.append(self)

			def Stop(self) -> None:
				self.stopped = True

		self.menuModule.wx.CallLater = Timer
		refresh = mock.Mock()
		menu = self.menuModule.CompanionMenu(
			"Companion",
			"Help",
			((self.menuModule.MenuSpec("Start", "", lambda event: None, lambda: True),),),
			refresh=refresh,
		)
		event = mock.Mock()
		event.GetMenu.return_value = menu._menu
		menu._onOpen(event)
		refresh.assert_called_once_with()
		timers[-1].function()
		self.assertEqual(refresh.call_count, 2)
		# Windows may report only the NVDA parent menu when the whole menu is dismissed.
		event.GetMenu.return_value = object()
		menu._onClose(event)
		self.assertTrue(timers[-1].stopped)
		timers[-1].function()
		self.assertEqual(refresh.call_count, 2)
		event.GetMenu.return_value = menu._menu
		menu._onOpen(event)
		self.assertEqual(refresh.call_count, 3)
		menu.terminate()
		self.assertTrue(timers[-1].stopped)

	def test_checkable_item_follows_its_setting(self) -> None:
		state = {"on": False}
		menu = self.menuModule.CompanionMenu(
			"Companion",
			"Help",
			((self.menuModule.MenuSpec("Auto", "", lambda event: None, isChecked=lambda: state["on"]),),),
		)
		(item,) = menu._menu.entries
		self.assertTrue(item.checkable)
		self.assertFalse(item.checked)
		state["on"] = True
		event = mock.Mock()
		(updateCheck,) = [
			handler for handler, source in self.owner.bound if handler.__name__ == "updateCheck"
		]
		updateCheck(event)
		event.Check.assert_called_once_with(True)
		menu.refreshEnabled()
		menu.terminate()
		self.assertEqual(len(self.owner.bound), len(self.owner.unbound))

	def test_plugin_menu_has_eleven_actions_including_recording(self) -> None:
		path = pathlib.Path(__file__).parents[1] / "addon/globalPlugins/whatsappWebPlusCompanion/__init__.py"
		source = path.read_text(encoding="utf-8")
		self.assertEqual(source.count("MenuSpec("), 11)
		self.assertIn("isChecked=settings.autoConnect", source)
		self.assertIn("self._onCallLabelsMenu", source)
		self.assertIn('_("Diagnose and repair WebView2 &policy permissions...")', source)
		self.assertIn("self._onDiagnoseRepairMenu", source)
		self.assertIn('_("&Check for WhatsApp Web Plus userscript updates")', source)
		self.assertNotIn("Open the checked WhatsApp Web Plus userscript update", source)


if __name__ == "__main__":
	unittest.main()
