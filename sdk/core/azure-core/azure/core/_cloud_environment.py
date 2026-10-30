# --------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# --------------------------------------------------------------------------
"""Resolves the cloud an application targets from the process environment.

``AZURE_CLOUD`` is the activation switch. When it names a built-in cloud, that cloud is
described and the other variables are ignored. Only the value ``custom`` causes
``AZURE_AUTHORITY_HOST``, ``AZURE_RESOURCE_MANAGER_ENDPOINT`` and
``AZURE_RESOURCE_MANAGER_AUDIENCE`` to be read, and then all three are required.

Configuration set in code always takes precedence: a client that specifies its own authority
host or endpoint is unaffected by these variables.
"""

import os
from typing import Optional

ENV_AZURE_CLOUD = "AZURE_CLOUD"
ENV_AZURE_AUTHORITY_HOST = "AZURE_AUTHORITY_HOST"
ENV_AZURE_RESOURCE_MANAGER_ENDPOINT = "AZURE_RESOURCE_MANAGER_ENDPOINT"
ENV_AZURE_RESOURCE_MANAGER_AUDIENCE = "AZURE_RESOURCE_MANAGER_AUDIENCE"

AZURE_CLOUD_NAME = "AzureCloud"
AZURE_US_GOVERNMENT_NAME = "AzureUSGovernment"
AZURE_CHINA_NAME = "AzureChinaCloud"
CUSTOM_NAME = "custom"

_AZURE_PUBLIC_AUTHORITY = "https://login.microsoftonline.com"
_AZURE_US_GOVERNMENT_AUTHORITY = "https://login.microsoftonline.us"
_AZURE_CHINA_AUTHORITY = "https://login.chinacloudapi.cn"

# Three vocabularies are in play for AZURE_CLOUD and all are accepted.
#
#   - "AzureCloud" and friends are the canonical cross-SDK spelling, matching `az cloud list`.
#   - "AZURE_PUBLIC_CLOUD" and friends are the values azure.core.AzureClouds and Java's
#     com.azure.core.models.AzureCloud already ship. Those DIVERGE from the canonical cross-SDK
#     spelling; the divergence predates this resolver and is preserved only for compatibility.
#   - "AZURE", "AZURE_CHINA" and "AZURE_US_GOVERNMENT" are Spring Cloud Azure's CloudType values.
#     Spring already maps AZURE_CLOUD onto its profile.cloud-type property, so rejecting them
#     would break applications that set this variable today.
_BUILT_IN = {
    "azurecloud": (AZURE_CLOUD_NAME, _AZURE_PUBLIC_AUTHORITY),
    "public": (AZURE_CLOUD_NAME, _AZURE_PUBLIC_AUTHORITY),
    "azure_public_cloud": (AZURE_CLOUD_NAME, _AZURE_PUBLIC_AUTHORITY),
    "azure": (AZURE_CLOUD_NAME, _AZURE_PUBLIC_AUTHORITY),
    "azureusgovernment": (AZURE_US_GOVERNMENT_NAME, _AZURE_US_GOVERNMENT_AUTHORITY),
    "usgovernment": (AZURE_US_GOVERNMENT_NAME, _AZURE_US_GOVERNMENT_AUTHORITY),
    "azure_us_government": (AZURE_US_GOVERNMENT_NAME, _AZURE_US_GOVERNMENT_AUTHORITY),
    "azurechinacloud": (AZURE_CHINA_NAME, _AZURE_CHINA_AUTHORITY),
    "china": (AZURE_CHINA_NAME, _AZURE_CHINA_AUTHORITY),
    "azure_china_cloud": (AZURE_CHINA_NAME, _AZURE_CHINA_AUTHORITY),
    "azure_china": (AZURE_CHINA_NAME, _AZURE_CHINA_AUTHORITY),
}


class CloudEnvironment:
    """Describes the cloud an application targets, as declared by the process environment.

    :param str name: canonical cloud name.
    :param str authority_host: base URL of the cloud's Microsoft Entra authority.
    :param resource_manager_endpoint: base URL of the cloud's Azure Resource Manager, or None
        for a built-in cloud whose endpoint is already known.
    :type resource_manager_endpoint: str or None
    :param resource_manager_audience: audience for Azure Resource Manager access tokens, or None
        for a built-in cloud whose audience is already known.
    :type resource_manager_audience: str or None
    """

    def __init__(
        self,
        name: str,
        authority_host: str,
        resource_manager_endpoint: Optional[str] = None,
        resource_manager_audience: Optional[str] = None,
    ) -> None:
        self.name = name
        self.authority_host = authority_host
        self.resource_manager_endpoint = resource_manager_endpoint
        self.resource_manager_audience = resource_manager_audience

    @property
    def is_custom(self) -> bool:
        """Whether this environment describes a custom cloud rather than a built-in one.

        :rtype: bool
        :return: True when the cloud is custom.
        """
        return self.resource_manager_endpoint is not None

    def __repr__(self) -> str:
        return "CloudEnvironment(name={!r}, authority_host={!r})".format(self.name, self.authority_host)


def _get(name: str) -> Optional[str]:
    value = os.environ.get(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _validate_https(variable: str, value: str) -> None:
    if not value.lower().startswith("https://"):
        raise ValueError("{} must use https. Got {!r}.".format(variable, value))
    if len(value) <= len("https://"):
        raise ValueError("{} must specify a host. Got {!r}.".format(variable, value))


def from_environment() -> Optional[CloudEnvironment]:
    """Resolve the cloud described by the process environment.

    :rtype: ~azure.core.CloudEnvironment or None
    :return: the resolved environment, or None when AZURE_CLOUD is not set.
    :raises ValueError: when AZURE_CLOUD names an unrecognized cloud, or is "custom" and the
        required endpoint variables are missing or malformed.
    """
    name = _get(ENV_AZURE_CLOUD)
    if name is None:
        return None

    key = name.lower()
    if key in _BUILT_IN:
        canonical, authority = _BUILT_IN[key]
        return CloudEnvironment(canonical, authority)

    if key == "other":
        # Spring Cloud Azure's CloudType.OTHER means "I configure endpoints myself", not "read
        # the endpoint variables". Treating it as a custom cloud would demand variables such an
        # application has never set, so it is treated as though AZURE_CLOUD were unset.
        return None

    if key == "azure_germany":
        raise ValueError(
            "{} names Microsoft Cloud Germany, which closed on October 29th, 2021.".format(ENV_AZURE_CLOUD)
        )

    if key != "custom":
        raise ValueError(
            "{} has unrecognized value {!r}. Valid values are {}, {}, {} and {}.".format(
                ENV_AZURE_CLOUD, name, AZURE_CLOUD_NAME, AZURE_US_GOVERNMENT_NAME, AZURE_CHINA_NAME, CUSTOM_NAME
            )
        )

    authority = _get(ENV_AZURE_AUTHORITY_HOST)
    endpoint = _get(ENV_AZURE_RESOURCE_MANAGER_ENDPOINT)
    audience = _get(ENV_AZURE_RESOURCE_MANAGER_AUDIENCE)

    missing = [
        variable
        for variable, value in (
            (ENV_AZURE_AUTHORITY_HOST, authority),
            (ENV_AZURE_RESOURCE_MANAGER_ENDPOINT, endpoint),
            (ENV_AZURE_RESOURCE_MANAGER_AUDIENCE, audience),
        )
        if value is None
    ]
    if missing:
        raise ValueError(
            '{} is "custom" but {} {} not set. A custom cloud requires all of {}, {} and {}.'.format(
                ENV_AZURE_CLOUD,
                ", ".join(missing),
                "is" if len(missing) == 1 else "are",
                ENV_AZURE_AUTHORITY_HOST,
                ENV_AZURE_RESOURCE_MANAGER_ENDPOINT,
                ENV_AZURE_RESOURCE_MANAGER_AUDIENCE,
            )
        )

    _validate_https(ENV_AZURE_AUTHORITY_HOST, authority)  # type: ignore[arg-type]
    _validate_https(ENV_AZURE_RESOURCE_MANAGER_ENDPOINT, endpoint)  # type: ignore[arg-type]
    _validate_https(ENV_AZURE_RESOURCE_MANAGER_AUDIENCE, audience)  # type: ignore[arg-type]

    return CloudEnvironment(CUSTOM_NAME, authority, endpoint, audience)  # type: ignore[arg-type]
