from collections.abc import Callable, Sequence
from dataclasses import dataclass

import gui
import wx


@dataclass(frozen=True, slots=True)
class MenuSpec:
	label: str
	helpText: str
	handler: Callable[[wx.CommandEvent], None]
	isEnabled: Callable[[], bool] | None = None
	isChecked: Callable[[], bool] | None = None


class CompanionMenu:
	def __init__(
		self,
		label: str,
		helpText: str,
		sections: Sequence[Sequence[MenuSpec]],
		*,
		refresh: Callable[[], None] | None = None,
	) -> None:
		super().__init__()
		mainFrame = gui.mainFrame
		if mainFrame is None:
			raise RuntimeError("NVDA main frame is not available")
		self._owner = mainFrame.sysTrayIcon
		self._toolsMenu = self._owner.toolsMenu
		self._menu = wx.Menu()
		self._bindings: list[tuple[wx.MenuItem, Callable[[wx.CommandEvent], None]]] = []
		self._updates = []
		self._open = False
		self._timer = None
		# Requests fresh state in the background while the submenu is open. Predicates stay cheap.
		self._refresh = refresh
		for sectionIndex, section in enumerate(sections):
			if sectionIndex:
				self._menu.AppendSeparator()
			for spec in section:
				if spec.isChecked is not None:
					item = self._menu.AppendCheckItem(wx.ID_ANY, spec.label, spec.helpText)
					item.Check(bool(spec.isChecked()))

					def updateCheck(event, predicate=spec.isChecked):
						event.Check(bool(predicate()))

					self._updates.append((item, None, updateCheck))
					self._owner.Bind(wx.EVT_UPDATE_UI, updateCheck, item)
				else:
					item = self._menu.Append(wx.ID_ANY, spec.label, spec.helpText)
				self._owner.Bind(wx.EVT_MENU, spec.handler, item)
				self._bindings.append((item, spec.handler))
				if spec.isEnabled is not None:
					item.Enable(False)

					def update(event, predicate=spec.isEnabled):
						event.Enable(bool(predicate()))

					self._owner.Bind(wx.EVT_UPDATE_UI, update, item)
					self._updates.append((item, spec.isEnabled, update))
		self._parentItem = self._toolsMenu.AppendSubMenu(self._menu, label, helpText)
		if self._updates:
			self._owner.Bind(wx.EVT_MENU_OPEN, self._onOpen)
			self._owner.Bind(wx.EVT_MENU_CLOSE, self._onClose)

	def refreshEnabled(self) -> None:
		for item, predicate, update in self._updates:
			if predicate is not None:
				item.Enable(bool(predicate()))

	def _onOpen(self, event) -> None:
		event.Skip()
		if event.GetMenu() is self._menu and not self._open:
			self._open = True
			self._tick()

	def _onClose(self, event) -> None:
		event.Skip()
		# A parent menu can only close after this submenu, and this submenu has no children, so any
		# close while it is open ends the refresh, even when Windows reports only the parent menu.
		if self._open or event.GetMenu() in (None, self._menu):
			self._stopRefresh()

	def _tick(self) -> None:
		if not self._open:
			return
		if self._refresh is not None:
			self._refresh()
		self.refreshEnabled()
		self._timer = wx.CallLater(2000, self._tick)

	def _stopRefresh(self) -> None:
		self._open = False
		if self._timer is not None:
			self._timer.Stop()
			self._timer = None

	def terminate(self) -> None:
		self._stopRefresh()
		if self._updates:
			self._owner.Unbind(wx.EVT_MENU_OPEN, handler=self._onOpen)
			self._owner.Unbind(wx.EVT_MENU_CLOSE, handler=self._onClose)
		for item, predicate, update in self._updates:
			self._owner.Unbind(wx.EVT_UPDATE_UI, handler=update, source=item)
		self._updates.clear()
		for item, handler in self._bindings:
			try:
				self._owner.Unbind(wx.EVT_MENU, handler=handler, source=item)
				self._menu.Remove(item.Id)
				item.Destroy()
			except (AttributeError, RuntimeError):
				pass
		self._bindings.clear()
		try:
			self._toolsMenu.Remove(self._parentItem.Id)
			self._parentItem.Destroy()
			self._menu.Destroy()
		except (AttributeError, RuntimeError):
			pass
