"""
Unit tests for parameter model validators.

Covers validation logic in source_params, repository_params,
and base_params that wasn't reached by integration tests.
"""

import pytest
from pydantic import ValidationError

from src.gramps_mcp.models.parameters.base_params import (
    BaseDataModel,
    BaseGetMultipleParams,
    BaseGetSingleParams,
)
from src.gramps_mcp.models.parameters.media_params import MediaSaveParams
from src.gramps_mcp.models.parameters.repository_params import (
    RepositoriesParams,
    RepositoryParams,
)
from src.gramps_mcp.models.parameters.source_params import (
    SourceDetailsParams,
    SourceSearchParams,
)


class TestBaseGetMultipleParamsValidators:
    """Test validators on BaseGetMultipleParams."""

    def test_valid_extend(self):
        params = BaseGetMultipleParams(extend="all")
        assert params.extend == "all"

    def test_valid_extend_multiple(self):
        params = BaseGetMultipleParams(extend="citation_list,note_list")
        assert params.extend == "citation_list,note_list"

    def test_invalid_extend(self):
        with pytest.raises(ValidationError) as exc_info:
            BaseGetMultipleParams(extend="invalid_choice")
        assert "Invalid extend choice" in str(exc_info.value)

    def test_extend_none(self):
        params = BaseGetMultipleParams(extend=None)
        assert params.extend is None

    def test_valid_profile(self):
        params = BaseGetMultipleParams(profile="all")
        assert params.profile == "all"

    def test_valid_profile_multiple(self):
        params = BaseGetMultipleParams(profile="self,families,events")
        assert params.profile == "self,families,events"

    def test_invalid_profile(self):
        with pytest.raises(ValidationError) as exc_info:
            BaseGetMultipleParams(profile="nonexistent")
        assert "Invalid profile choice" in str(exc_info.value)

    def test_profile_none(self):
        params = BaseGetMultipleParams(profile=None)
        assert params.profile is None

    def test_extend_with_spaces(self):
        params = BaseGetMultipleParams(extend="citation_list, note_list")
        assert params.extend == "citation_list, note_list"


class TestBaseGetSingleParamsValidators:
    """Test validators on BaseGetSingleParams."""

    def test_valid_extend(self):
        params = BaseGetSingleParams(extend="all")
        assert params.extend == "all"

    def test_invalid_extend(self):
        with pytest.raises(ValidationError) as exc_info:
            BaseGetSingleParams(extend="bogus")
        assert "Invalid extend choice" in str(exc_info.value)

    def test_valid_profile(self):
        params = BaseGetSingleParams(profile="self")
        assert params.profile == "self"

    def test_invalid_profile(self):
        with pytest.raises(ValidationError) as exc_info:
            BaseGetSingleParams(profile="bogus")
        assert "Invalid profile choice" in str(exc_info.value)


class TestBaseDataModel:
    """Test BaseDataModel fields and defaults."""

    def test_list_mode_default(self):
        # BaseDataModel requires no fields
        model = BaseDataModel()
        assert model.list_mode == "merge"

    def test_list_mode_replace(self):
        model = BaseDataModel(list_mode="replace")
        assert model.list_mode == "replace"

    def test_list_mode_invalid(self):
        with pytest.raises(ValidationError):
            BaseDataModel(list_mode="invalid")

    def test_all_optional_fields(self):
        model = BaseDataModel()
        assert model.handle is None
        assert model.gramps_id is None
        assert model.note_list is None
        assert model.media_list is None
        assert model.attribute_list is None
        assert model.tag_list is None
        assert model.private is None
        assert model.change is None


class TestSourceSearchParamsValidators:
    """Test source-specific validators."""

    def test_valid_sort(self):
        params = SourceSearchParams(sort="title")
        assert params.sort == "title"

    def test_valid_sort_descending(self):
        params = SourceSearchParams(sort="-author")
        assert params.sort == "-author"

    def test_valid_sort_multiple(self):
        params = SourceSearchParams(sort="title,-author")
        assert params.sort == "title,-author"

    def test_invalid_sort(self):
        with pytest.raises(ValidationError) as exc_info:
            SourceSearchParams(sort="invalid_key")
        assert "Invalid sort key" in str(exc_info.value)

    def test_sort_none(self):
        params = SourceSearchParams(sort=None)
        assert params.sort is None

    def test_valid_extend_source_specific(self):
        params = SourceSearchParams(extend="reporef_list")
        assert params.extend == "reporef_list"

    def test_invalid_extend_source_specific(self):
        # event_ref_list is valid for base but not for source
        with pytest.raises(ValidationError) as exc_info:
            SourceSearchParams(extend="event_ref_list")
        assert "Invalid extend choice" in str(exc_info.value)


class TestSourceDetailsParamsValidators:
    """Test source detail validators."""

    def test_valid_extend(self):
        params = SourceDetailsParams(extend="all")
        assert params.extend == "all"

    def test_invalid_extend(self):
        with pytest.raises(ValidationError) as exc_info:
            SourceDetailsParams(extend="event_ref_list")
        assert "Invalid extend choice" in str(exc_info.value)


class TestRepositoriesParamsValidators:
    """Test repository-specific validators."""

    def test_valid_sort(self):
        params = RepositoriesParams(sort="name")
        assert params.sort == "name"

    def test_valid_sort_descending(self):
        params = RepositoriesParams(sort="-type")
        assert params.sort == "-type"

    def test_invalid_sort(self):
        with pytest.raises(ValidationError) as exc_info:
            RepositoriesParams(sort="title")
        assert "Invalid sort key" in str(exc_info.value)

    def test_sort_none(self):
        params = RepositoriesParams(sort=None)
        assert params.sort is None

    def test_valid_extend_repo_specific(self):
        params = RepositoriesParams(extend="note_list")
        assert params.extend == "note_list"

    def test_invalid_extend_repo_specific(self):
        with pytest.raises(ValidationError) as exc_info:
            RepositoriesParams(extend="media_list")
        assert "Invalid extend choice" in str(exc_info.value)


class TestRepositoryParamsValidators:
    """Test single repository detail validators."""

    def test_valid_extend(self):
        params = RepositoryParams(extend="all")
        assert params.extend == "all"

    def test_invalid_extend(self):
        with pytest.raises(ValidationError) as exc_info:
            RepositoryParams(extend="citation_list")
        assert "Invalid extend choice" in str(exc_info.value)


class TestMediaSaveParams:
    """Unit tests for MediaSaveParams schema shape — no network required."""

    def test_file_location_field_exists(self):
        assert "file_location" in MediaSaveParams.model_fields

    def test_file_location_is_optional(self):
        field = MediaSaveParams.model_fields["file_location"]
        assert not field.is_required()

    def test_description_field_absent(self):
        # description is a no-op duplicate of desc — it must not appear
        assert "description" not in MediaSaveParams.model_fields

    def test_desc_is_create_required(self):
        """desc is Optional at field level but enforced on create by model_validator."""
        field = MediaSaveParams.model_fields["desc"]
        assert not field.is_required()
        # Create without desc (no handle) should fail
        with pytest.raises(ValueError, match="desc"):
            MediaSaveParams()

    def test_instantiation_without_file_location_succeeds(self):
        # Update path: only metadata, no file upload
        params = MediaSaveParams(handle="abc123", desc="A photo")
        assert params.file_location is None

    def test_instantiation_with_file_location_succeeds(self):
        # Create path: file upload
        params = MediaSaveParams(desc="A photo", file_location="/tmp/photo.jpg")
        assert params.file_location == "/tmp/photo.jpg"
