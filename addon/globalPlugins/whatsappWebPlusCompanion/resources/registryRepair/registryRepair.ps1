# WhatsApp Companion - fixed-purpose elevated registry permission repair.
# Deviates from the original plan's native C++ helper by project-owner decision.
#
# Exit-code ABI (stable):
# 0 repaired                      8 mutex busy
# 1 already correct               9 key open/create failure
# 2 invalid protocol              10 explicit deny / managed ACL
# 3 not elevated                  11 insufficient WRITE_DAC rights
# 4 parent process missing        12 DACL apply failure
# 5 parent creation-time mismatch 13 verification failed, rollback succeeded
# 6 parent SID mismatch           14 rollback failed
# 7 user hive unavailable         15 internal failure
param(
	[Parameter(Mandatory = $true)][int]$ProtocolVersion,
	[Parameter(Mandatory = $true)][int]$ParentPid,
	[Parameter(Mandatory = $true)][string]$ParentCreationTicks,
	[Parameter(Mandatory = $true)][string]$RequestedSid
)

$ErrorActionPreference = 'Stop'
$requiredRights = [System.Security.AccessControl.RegistryRights]::QueryValues -bor [System.Security.AccessControl.RegistryRights]::SetValue
$openRights = [System.Security.AccessControl.RegistryRights]::ChangePermissions -bor [System.Security.AccessControl.RegistryRights]::ReadPermissions -bor [System.Security.AccessControl.RegistryRights]::QueryValues
$sidPattern = '^S-1-\d+-\d+(?:-\d+)+$'
$toleranceTicks = 20000000 # 2 seconds; PID-reuse protection does not need tick precision.
function Get-AceSid($ace) {
	# RegistrySecurity.Access exposes IdentityReference as an account name
	# (NTAccount), never as the SID string. Translate it back for comparisons.
	try {
		return ([System.Security.Principal.SecurityIdentifier]($ace.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]))).Value
	} catch {
		return ""
	}
}
trap {
	exit 15
}

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

public static class WwpAccessCheck {
	[StructLayout(LayoutKind.Sequential)]
	private struct GENERIC_MAPPING {
		public uint GenericRead, GenericWrite, GenericExecute, GenericAll;
	}

	[DllImport("kernel32.dll", SetLastError = true)]
	private static extern IntPtr OpenProcess(uint access, bool inherit, uint pid);
	[DllImport("kernel32.dll", SetLastError = true)]
	private static extern bool CloseHandle(IntPtr h);
	[StructLayout(LayoutKind.Sequential)]
	private struct FILETIME {
		public uint dwLowDateTime, dwHighDateTime;
	}
	[DllImport("kernel32.dll", SetLastError = true)]
	private static extern bool GetProcessTimes(
		IntPtr process,
		out FILETIME creation,
		out FILETIME exitTime,
		out FILETIME kernel,
		out FILETIME user
	);
	[DllImport("advapi32.dll", SetLastError = true)]
	private static extern bool GetTokenInformation(
		IntPtr token,
		int tokenInformationClass,
		byte[] buffer,
		uint bufferLength,
		out uint returnLength
	);
	[DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
	private static extern bool ConvertSidToStringSid(IntPtr sid, out IntPtr sidString);
	[DllImport("kernel32.dll", SetLastError = true)]
	private static extern IntPtr LocalFree(IntPtr hMem);
	[StructLayout(LayoutKind.Sequential)]
	private struct SID_AND_ATTRIBUTES {
		public IntPtr Sid;
		public uint Attributes;
	}
	[StructLayout(LayoutKind.Sequential)]
	private struct TOKEN_USER {
		public SID_AND_ATTRIBUTES User;
	}
	[DllImport("advapi32.dll", SetLastError = true)]
	private static extern bool OpenProcessToken(IntPtr process, uint access, out IntPtr token);
	[DllImport("advapi32.dll", SetLastError = true)]
	private static extern bool DuplicateToken(IntPtr token, int level, out IntPtr duplicated);
	[DllImport("advapi32.dll", SetLastError = true)]
	private static extern int RegGetKeySecurity(SafeRegistryHandle key, int securityInfo, byte[] descriptor, ref uint size);
	[DllImport("advapi32.dll", SetLastError = true)]
	private static extern bool AccessCheck(
		byte[] descriptor,
		IntPtr clientToken,
		uint desiredAccess,
		GENERIC_MAPPING[] genericMapping,
		byte[] privilegeSet,
		ref uint privilegeSetLength,
		out uint grantedAccess,
		out bool accessStatus
	);

	public static bool CanAccess(uint parentPid, Microsoft.Win32.RegistryKey key, uint requiredRights) {
		IntPtr process = OpenProcess(0x1000, false, parentPid); // PROCESS_QUERY_LIMITED_INFORMATION
		if (process == IntPtr.Zero) return false;
		try {
			IntPtr token;
			if (!OpenProcessToken(process, 0x0008 | 0x0002, out token)) return false;
			try {
				IntPtr duplicated;
				if (!DuplicateToken(token, 2, out duplicated)) return false; // SecurityImpersonation
				try {
					uint size = 0;
					int result = RegGetKeySecurity(key.Handle, 7, null, ref size); // OWNER|GROUP|DACL
					if (result != 234 && result != 122 && result != 0) return false; // 234/122 = buffer too small
					byte[] descriptor = new byte[size];
					result = RegGetKeySecurity(key.Handle, 7, descriptor, ref size);
					if (result != 0) return false;
					byte[] privilegeSet = new byte[1024];
					uint privilegeSetLength = (uint)privilegeSet.Length;
					uint granted = 0;
					bool accessStatus = false;
					if (!AccessCheck(
						descriptor,
						duplicated,
						requiredRights,
						new GENERIC_MAPPING[1],
						privilegeSet,
						ref privilegeSetLength,
						out granted,
						out accessStatus
					)) return false;
					return accessStatus;
				} finally {
					CloseHandle(duplicated);
				}
			} finally {
				CloseHandle(token);
			}
		} finally {
			CloseHandle(process);
		}
	}

	public static bool TryGetProcessCreationTicks(uint pid, out ulong ticks) {
		IntPtr process = OpenProcess(0x1000, false, pid);
		if (process == IntPtr.Zero) {
			ticks = 0;
			return false;
		}
		try {
			FILETIME creation, exitTime, kernel, user;
			if (!GetProcessTimes(process, out creation, out exitTime, out kernel, out user)) {
				ticks = 0;
				return false;
			}
			ticks = ((ulong)creation.dwHighDateTime << 32) | creation.dwLowDateTime;
			return true;
		} finally {
			CloseHandle(process);
		}
	}

	public static bool TryGetProcessUserSid(uint pid, out string sid) {
		sid = "";
		IntPtr process = OpenProcess(0x1000, false, pid);
		if (process == IntPtr.Zero) return false;
		try {
			IntPtr token;
			if (!OpenProcessToken(process, 0x0008, out token)) return false; // TOKEN_QUERY
			try {
				byte[] buffer = new byte[1024];
				uint length = 0;
				if (!GetTokenInformation(token, 1, buffer, (uint)buffer.Length, out length)) return false; // TokenUser
				GCHandle pin = GCHandle.Alloc(buffer, GCHandleType.Pinned);
				try {
					TOKEN_USER tokenUser = (TOKEN_USER)Marshal.PtrToStructure(pin.AddrOfPinnedObject(), typeof(TOKEN_USER));
					if (tokenUser.User.Sid == IntPtr.Zero) return false;
					IntPtr sidString;
					if (!ConvertSidToStringSid(tokenUser.User.Sid, out sidString)) return false;
					try {
						sid = Marshal.PtrToStringUni(sidString);
						return !string.IsNullOrEmpty(sid);
					} finally {
						LocalFree(sidString);
					}
				} finally {
					pin.Free();
				}
			} finally {
				CloseHandle(token);
			}
		} finally {
			CloseHandle(process);
		}
	}
}
'@

if ($ProtocolVersion -ne 1) { exit 2 }
$identity = New-Object System.Security.Principal.WindowsIdentity([System.Security.Principal.WindowsIdentity]::GetCurrent().Token)
$principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) { exit 3 }
if ($RequestedSid -notmatch $sidPattern) { exit 6 }

$creationTicks = [uint64]0
if (-not [WwpAccessCheck]::TryGetProcessCreationTicks([uint32]$ParentPid, [ref]$creationTicks)) { exit 4 }
if ([Math]::Abs([long]$creationTicks - [long]$ParentCreationTicks) -gt $toleranceTicks) { exit 5 }
$parentSid = ""
if (-not [WwpAccessCheck]::TryGetProcessUserSid([uint32]$ParentPid, [ref]$parentSid)) { exit 6 }
if ($parentSid -ine $RequestedSid) { exit 6 }
$serviceSids = @('S-1-5-18', 'S-1-5-19', 'S-1-5-20')
if ($serviceSids -contains $RequestedSid) { exit 6 }

$mutex = $null
try {
	$mutex = New-Object System.Threading.Mutex($false, 'Local\WhatsAppWebPlusCompanionRegistryLease')
} catch {
	exit 15
}
if (-not $mutex.WaitOne(0)) {
	$mutex.Dispose()
	exit 8
}

$fullPath = "$RequestedSid\Software\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments"
$root = [Microsoft.Win32.Registry]::Users
try {
	$hive = $root.OpenSubKey($RequestedSid)
	if ($null -eq $hive) { exit 7 }
	$hive.Close()
	$created = $null -eq $root.OpenSubKey($fullPath)
	$leaf = $root.CreateSubKey($fullPath)
	if ($null -eq $leaf) { exit 9 }
	$leaf.Close()
	$key = $root.OpenSubKey($fullPath, [Microsoft.Win32.RegistryKeyPermissionCheck]::ReadWriteSubTree, $openRights)
	if ($null -eq $key) { exit 11 }

	$originalAcl = $key.GetAccessControl([System.Security.AccessControl.AccessControlSections]::Access)
	$originalDacl = $originalAcl.GetSecurityDescriptorBinaryForm()
	$restoreSecurity = New-Object System.Security.AccessControl.RegistrySecurity
	$restoreSecurity.SetSecurityDescriptorBinaryForm($originalDacl)

	$denyPresent = $false
	$allowSufficient = $false
	foreach ($ace in $originalAcl.Access) {
		if ((Get-AceSid $ace) -ieq $RequestedSid) {
			if ($ace.AccessControlType -eq [System.Security.AccessControl.AccessControlType]::Deny) {
				$denyPresent = $true
			} elseif (($ace.RegistryRights -band $requiredRights) -eq $requiredRights) {
				$allowSufficient = $true
			}
		}
	}
	if ($denyPresent) { exit 10 }
	if ($allowSufficient) { exit 1 }

	$rule = New-Object System.Security.AccessControl.RegistryAccessRule(
		(New-Object System.Security.Principal.SecurityIdentifier($RequestedSid)),
		$requiredRights,
		[System.Security.AccessControl.InheritanceFlags]::None,
		[System.Security.AccessControl.PropagationFlags]::None,
		[System.Security.AccessControl.AccessControlType]::Allow
	)
	$modifiedAcl = $key.GetAccessControl([System.Security.AccessControl.AccessControlSections]::Access)
	$modifiedAcl.AddAccessRule($rule)
	try {
		$key.SetAccessControl($modifiedAcl)
	} catch {
		try {
			$key.SetAccessControl($restoreSecurity)
			exit 12
		} catch {
			exit 14
		}
	}

	$verified = $false
	$verifyAcl = $key.GetAccessControl([System.Security.AccessControl.AccessControlSections]::Access)
	foreach ($ace in $verifyAcl.Access) {
		$aceSid = Get-AceSid $ace
		if (
			$aceSid -ieq $RequestedSid -and
			$ace.AccessControlType -eq [System.Security.AccessControl.AccessControlType]::Allow -and
			($ace.RegistryRights -band $requiredRights) -eq $requiredRights
		) {
			$verified = $true
		}
	}
	if ($verified -and -not [WwpAccessCheck]::CanAccess(
		[uint32]$ParentPid,
		$key,
		[uint32]$requiredRights
	)) {
		$verified = $false
	}
	if (-not $verified) {
		try {
			$key.SetAccessControl($restoreSecurity)
		} catch {
			exit 14
		}
		if ($created) {
			try {
				if ($key.SubKeyCount -eq 0 -and $key.ValueCount -eq 0) {
					$root.DeleteSubKey($fullPath, $false)
				}
			} catch {
				# Evidence of an empty created leaf may remain; do not mask rollback success.
			}
		}
		exit 13
	}
	exit 0
} catch {
	# A later failure must still leave the DACL unchanged (plan: restore on
	# failure). Best effort; the journal and postcheck remain the backstop.
	if ($null -ne $key -and $null -ne $restoreSecurity) {
		try { $key.SetAccessControl($restoreSecurity) } catch { }
	}
	exit 15
} finally {
	if ($null -ne $mutex) {
		try { $mutex.ReleaseMutex() } catch { }
		$mutex.Dispose()
	}
	if ($null -ne $key) { $key.Dispose() }
}
