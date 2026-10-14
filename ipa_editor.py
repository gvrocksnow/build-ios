import os
import plistlib
import re
import zipfile

# Optional version overrides, read from the environment (main.py loads .env first).
# App Store Connect rejects an upload whose CFBundleVersion was already used, so
# bump IPA_BUILD_VERSION for every upload.
SHORT_VERSION_ENV = "IPA_SHORT_VERSION"  # CFBundleShortVersionString, e.g. 1.0.4
BUILD_VERSION_ENV = "IPA_BUILD_VERSION"  # CFBundleVersion, e.g. 1.0.4

INFO_PLIST_RE = re.compile(r"^Payload/[^/]+\.app/Info\.plist$")


def patch_info_plist(data: bytes) -> bytes:
    """
    Sets the app's version fields from the environment, keeping the plist format.

    Args:
        data (bytes): The original Info.plist contents.

    Returns:
        bytes: The patched Info.plist contents, or the original if nothing is set.
    """

    short_version = os.getenv(SHORT_VERSION_ENV)
    build_version = os.getenv(BUILD_VERSION_ENV)
    if not short_version and not build_version:
        return data

    fmt = plistlib.FMT_BINARY if data.startswith(b"bplist") else plistlib.FMT_XML
    info = plistlib.loads(data)

    if short_version:
        print(f"CFBundleShortVersionString: {info.get('CFBundleShortVersionString')} -> {short_version}")
        info["CFBundleShortVersionString"] = short_version
    if build_version:
        print(f"CFBundleVersion: {info.get('CFBundleVersion')} -> {build_version}")
        info["CFBundleVersion"] = build_version

    return plistlib.dumps(info, fmt=fmt)


def replace_pck(ipa_path: str) -> None:
    """
    Replaces .pck file in a given IPA file, and sets the version fields in
    Info.plist when IPA_SHORT_VERSION / IPA_BUILD_VERSION are set.

    Args:
        ipa_path (str): The path to the IPA file.
    """

    replacement_path = f"Payload/{ipa_path[0:-4]}.app/{ipa_path[0:-4]}.pck"
    pck_file = f"{ipa_path[0:-4]}.pck"

    with (
        zipfile.ZipFile(ipa_path) as ipa,
        zipfile.ZipFile("temp_ipa.ipa", "w") as tmp_ipa,
    ):
        for item in ipa.infolist():
            if item.filename == replacement_path:
                with open(pck_file, "rb") as file:
                    tmp_ipa.writestr(replacement_path, file.read())
            elif INFO_PLIST_RE.match(item.filename):
                tmp_ipa.writestr(item, patch_info_plist(ipa.read(item.filename)))
            else:
                tmp_ipa.writestr(item, ipa.read(item.filename))

    os.replace("temp_ipa.ipa", ipa_path)
