"""Restore only the observed compact call via its native accessibility action."""

import time

from . import CallAction, labels

PEER_NAME = "WhatsApp.PeerStreamVm"
MUTE_NAMES = labels.COMPACT_MUTE_LABELS


def kind(element, pid):
	if (
		element.currentProcessId != pid
		or element.currentFrameworkId != "XAML"
		or not element.currentIsEnabled
		or element.currentIsOffscreen
	):
		return None
	name = " ".join(element.currentName.split())
	if (
		element.currentControlType == 50007
		and element.currentClassName == "ListViewItem"
		and name == PEER_NAME
	):
		return "peer"
	if (
		element.currentControlType == 50002
		and element.currentClassName == "CheckBox"
		and labels.matches(CallAction.MUTE, name, MUTE_NAMES)
	):
		return "mute"
	return None


def findCompact(root, walker, pid, *, clock=time.monotonic):
	"""A complete bounded scan must show one peer and one mute in one host."""
	deadline = clock() + 0.25
	stack = [(root, 0, 0)]
	matches = {"peer": [], "mute": []}
	count = 0
	while stack:
		if count >= 100 or clock() >= deadline:
			return None
		el, depth, host = stack.pop()
		count += 1
		if el.currentProcessId != pid:
			continue
		if el.currentClassName == "InputSiteWindowClass":
			host = el.currentNativeWindowHandle
		# Expanded/incoming controls make this compact signature ambiguous.
		if el.currentControlType == 50000:
			if labels.buttonAction(el.currentName) is not None:
				return None
		category = kind(el, pid)
		if category and host:
			matches[category].append((el, host))
		child = walker.GetFirstChildElement(el)
		if child and depth >= 12:
			return None
		while child:
			if count + len(stack) >= 100 or clock() >= deadline:
				return None
			stack.append((child, depth + 1, host))
			child = walker.GetNextSiblingElement(child)
	if any(len(items) != 1 for items in matches.values()):
		return None
	peer, mute = matches["peer"][0], matches["mute"][0]
	return (peer[0], mute[0], peer[1]) if peer[1] == mute[1] else None


def restore(candidate, pid, *, contextValid, belongsToWindow, getLegacy):
	"""One native default action; never click coordinates or retry uncertainty."""
	peer, mute, host = candidate

	def valid():
		return (
			kind(peer, pid) == "peer"
			and kind(mute, pid) == "mute"
			and belongsToWindow(host)
			and contextValid()
		)

	if not valid():
		return False
	pattern = getLegacy(peer)
	if not pattern:
		return False
	defaultAction = pattern.CurrentDefaultAction
	if not isinstance(defaultAction, str) or not defaultAction.strip():
		return False
	if not valid():
		return False
	pattern.DoDefaultAction()
	return True
