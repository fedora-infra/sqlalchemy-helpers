# SPDX-FileCopyrightText: 2023 Contributors to the Fedora Project
#
# SPDX-License-Identifier: LGPL-3.0-or-later


def assert_partial_call(call, expected_args=None, expected_kwargs=None):
    assert (
        expected_args is not None or expected_kwargs is not None
    ), "Wrong usage of assert_partial_call: use at least one of expected_args or expected_kwargs"
    if expected_args is not None:
        assert set(expected_args).issubset(call)  # TODO: this does not check the order
    if expected_args is not None:
        for key, value in expected_kwargs.items():
            assert key in call.kwargs
            assert call.kwargs[key] == value
