from collections.abc import Callable
from typing import Any

import wx


MessageDialog: Any
Payload: Any

try:
	from gui.message import MessageDialog as _NativeMessageDialog
	from gui.message import Payload as _NativePayload
except ImportError:
	from gui import message as guiMessage

	_DEFAULT_BUTTONS = object()

	class _CompatPayload:
		pass

	class _DestroyEvent:
		def __init__(self, dialog: "_CompatMessageDialog") -> None:
			super().__init__()
			self._dialog = dialog

		def GetEventObject(self) -> "_CompatMessageDialog":
			return self._dialog

		def Skip(self) -> None:
			pass

	class _CompatMessageDialog:
		"""Compatibility wrapper for NVDA versions before MessageDialog."""

		def __init__(
			self,
			parent: wx.Window,
			message: str,
			caption: str = wx.MessageBoxCaptionStr,
			buttons: object = _DEFAULT_BUTTONS,
		) -> None:
			super().__init__()
			self._parent = parent
			self._message = message
			self._caption = caption
			self._customButtons = buttons is None
			self._noLabel = ""
			self._yesLabel = ""
			self._defaultOnNo = False
			self._yesCallback: Callable[[_CompatPayload], None] | None = None
			self._destroyHandler: Callable[[_DestroyEvent], None] | None = None
			self._nativeDialog: wx.MessageDialog | None = None

		def addNoButton(
			self,
			*,
			label: str,
			defaultFocus: bool = False,
			fallbackAction: bool = False,
		) -> "_CompatMessageDialog":
			self._noLabel = label
			# The safe button is the default action: Enter cancels. On the legacy
			# path this also approximates fallbackAction, which is a modern API
			# concept without a native wx.MessageDialog equivalent.
			self._defaultOnNo = self._defaultOnNo or defaultFocus
			return self

		def addYesButton(
			self,
			*,
			label: str,
			callback: Callable[[_CompatPayload], None],
		) -> "_CompatMessageDialog":
			self._yesLabel = label
			self._yesCallback = callback
			return self

		def Bind(self, eventType: object, handler: Callable[[_DestroyEvent], None]) -> None:
			if eventType == wx.EVT_WINDOW_DESTROY:
				self._destroyHandler = handler

		@staticmethod
		def _withoutMnemonic(label: str) -> str:
			return label.replace("&&", "\0").replace("&", "").replace("\0", "&")

		def Show(self) -> None:
			style = (
				wx.OK | wx.CANCEL | wx.ICON_QUESTION | wx.CENTER if self._customButtons else wx.OK | wx.CENTER
			)
			if self._customButtons:
				if self._defaultOnNo:
					style |= getattr(wx, "CANCEL_DEFAULT", 0)
				else:
					style |= getattr(wx, "OK_DEFAULT", 0)
			dialog = wx.MessageDialog(
				self._parent,
				self._message,
				self._caption,
				style,
			)
			self._nativeDialog = dialog
			if self._customButtons and hasattr(dialog, "SetOKCancelLabels"):
				dialog.SetOKCancelLabels(
					self._withoutMnemonic(self._yesLabel),
					self._withoutMnemonic(self._noLabel),
				)
			confirmed = False
			try:
				confirmed = guiMessage.displayDialogAsModal(dialog) in (wx.ID_OK, wx.OK)
			finally:
				self._nativeDialog = None
				dialog.Destroy()
			try:
				if confirmed and self._yesCallback is not None:
					self._yesCallback(_CompatPayload())
			finally:
				if self._destroyHandler is not None:
					self._destroyHandler(_DestroyEvent(self))

		def Raise(self) -> None:
			if self._nativeDialog is not None:
				self._nativeDialog.Raise()

		def SetFocus(self) -> None:
			if self._nativeDialog is not None:
				self._nativeDialog.SetFocus()

		def Close(self) -> None:
			if self._nativeDialog is not None:
				self._nativeDialog.Close()

	Payload = _CompatPayload
	MessageDialog = _CompatMessageDialog
else:
	Payload = _NativePayload
	MessageDialog = _NativeMessageDialog
