from collections.abc import Callable, Sequence
from dataclasses import dataclass

import gui
import wx


@dataclass(frozen=True, slots=True)
class MenuSpec:
	label: str
	helpText: str
	handler: Callable[[wx.CommandEvent], None]


class CompanionMenu:
	def __init__(
		self,
		label: str,
		helpText: str,
		sections: Sequence[Sequence[MenuSpec]],
	) -> None:
		super().__init__()
		mainFrame = gui.mainFrame
		if mainFrame is None:
			raise RuntimeError("NVDA main frame is not available")
		self._owner = mainFrame.sysTrayIcon
		self._toolsMenu = self._owner.toolsMenu
		self._menu = wx.Menu()
		self._bindings: list[tuple[wx.MenuItem, Callable[[wx.CommandEvent], None]]] = []
		for sectionIndex, section in enumerate(sections):
			if sectionIndex:
				self._menu.AppendSeparator()
			for spec in section:
				item = self._menu.Append(wx.ID_ANY, spec.label, spec.helpText)
				self._owner.Bind(wx.EVT_MENU, spec.handler, item)
				self._bindings.append((item, spec.handler))
		self._parentItem = self._toolsMenu.AppendSubMenu(self._menu, label, helpText)

	def terminate(self) -> None:
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
