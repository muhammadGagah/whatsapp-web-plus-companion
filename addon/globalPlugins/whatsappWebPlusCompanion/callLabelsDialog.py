"""Native editor for additional call labels; changes are staged until Save."""

import addonHandler
import wx

from appModules.wwpCallSupport import CallAction
from appModules.wwpCallSupport import labels

addonHandler.initTranslation()


def actionNames():
	return {
		CallAction.ANSWER: _("Answer incoming call"),
		CallAction.DECLINE: _("Decline incoming call"),
		CallAction.CAMERA: _("Camera on/off"),
		CallAction.MUTE: _("Microphone mute/unmute (including compact view)"),
		CallAction.REACTIONS: _("Reactions"),
		CallAction.HAND: _("Raise/lower hand"),
		CallAction.SHARE: _("Start/stop screen sharing"),
		CallAction.END: _("End call"),
	}


class CallLabelsDialog(wx.Dialog):
	def __init__(self, parent, *, onSaved, allowed):
		# Read before creating a native window so a load failure cannot leak a dialog.
		drafts = labels.loadOverrides()
		super().__init__(
			parent, title=_("Call control labels"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
		)
		self._drafts = drafts
		self._onSaved = onSaved
		self._allowed = allowed
		self._names = actionNames()
		self._actions = list(self._names)
		self._index = 0
		outer = wx.BoxSizer(wx.VERTICAL)
		intro = wx.StaticText(
			self,
			label=_(
				"Add the exact labels spoken by NVDA for WhatsApp call controls, one per line. "
				"For toggles, include both states. Built-in labels remain available; blank uses only built-in labels. "
				"Changes apply to all WhatsApp channels after Save."
			),
		)
		intro.Wrap(560)
		outer.Add(intro, flag=wx.ALL | wx.EXPAND, border=10)
		outer.Add(wx.StaticText(self, label=_("&Call action:")), flag=wx.LEFT | wx.RIGHT, border=10)
		self.action = wx.Choice(self, choices=list(self._names.values()))
		self.action.SetSelection(0)
		outer.Add(self.action, flag=wx.ALL | wx.EXPAND, border=10)
		outer.Add(
			wx.StaticText(self, label=_("&Built-in labels (read only):")), flag=wx.LEFT | wx.RIGHT, border=10
		)
		self.defaults = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 90))
		outer.Add(self.defaults, flag=wx.ALL | wx.EXPAND, border=10)
		outer.Add(
			wx.StaticText(self, label=_("&Additional labels (one per line):")),
			flag=wx.LEFT | wx.RIGHT,
			border=10,
		)
		self.custom = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(-1, 120))
		outer.Add(self.custom, proportion=1, flag=wx.ALL | wx.EXPAND, border=10)
		reset = wx.Button(self, label=_("&Reset all additional labels"))
		outer.Add(reset, flag=wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)
		buttons = wx.StdDialogButtonSizer()
		save = wx.Button(self, wx.ID_OK, label=_("&Save"))
		cancel = wx.Button(self, wx.ID_CANCEL, label=_("Cancel"))
		buttons.AddButton(save)
		buttons.AddButton(cancel)
		buttons.Realize()
		outer.Add(buttons, flag=wx.ALL | wx.ALIGN_RIGHT, border=10)
		self.SetSizerAndFit(outer)
		self.SetMinSize(self.GetSize())
		save.SetDefault()
		self.SetEscapeId(wx.ID_CANCEL)
		self.action.Bind(wx.EVT_CHOICE, self._selectAction)
		reset.Bind(wx.EVT_BUTTON, self._reset)
		save.Bind(wx.EVT_BUTTON, self._save)
		cancel.Bind(wx.EVT_BUTTON, lambda event: self.Close())
		self.Bind(wx.EVT_CLOSE, lambda event: self.Destroy())
		self._displayAction()
		self.CentreOnScreen()
		self.action.SetFocus()

	def _stageAction(self):
		self._drafts[self._actions[self._index].value] = self.custom.GetValue()

	def _displayAction(self):
		action = self._actions[self._index]
		self.defaults.ChangeValue("\n".join(labels.defaultLabels(action)))
		self.custom.ChangeValue(self._drafts.get(action.value, ""))

	def _selectAction(self, event):
		self._stageAction()
		self._index = self.action.GetSelection()
		self._displayAction()

	def _error(self, message):
		with wx.MessageDialog(self, message, _("Call control labels"), wx.OK | wx.ICON_ERROR) as dialog:
			dialog.ShowModal()
		self.custom.SetFocus()

	def _reset(self, event):
		self._drafts = {}
		self._displayAction()
		with wx.MessageDialog(
			self,
			_(
				"Additional labels cleared in this dialog. Choose Save to apply, or Cancel to keep your saved labels."
			),
			_("Call control labels"),
			wx.OK | wx.ICON_INFORMATION,
		) as dialog:
			dialog.ShowModal()
		self.custom.SetFocus()

	def _save(self, event):
		if not self._allowed():
			self.Close()
			return
		self._stageAction()
		try:
			labels.saveOverrides(self._drafts)
		except labels.ValidationError as error:
			if error.action in self._drafts:
				self._index = self._actions.index(CallAction(error.action))
				self.action.SetSelection(self._index)
				self._displayAction()
			self._error(
				_(
					"Could not save labels for {action}. Use at most 20 labels per action, each at most 128 characters. "
					"The same label cannot belong to different actions. Check the selected action."
				).format(action=self._names[self._actions[self._index]])
			)
			return
		except Exception:
			self._error(
				_("Could not save call control labels. Your changes are still in this dialog. Try again.")
			)
			return
		self.Close()
		self._onSaved()
