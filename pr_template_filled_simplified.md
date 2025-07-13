## PR Title

**fix: Fix o3-pro empty response issue by using output_text field**

## Summary

Fixes o3-pro API calls returning empty responses due to incorrect response parsing. The code was trying to parse `response.output.content[]` array, but o3-pro provides `output_text` directly.

## Changes

- Fixed o3-pro response parsing to use `output_text` field
- Added `_safe_extract_output_text` method with validation
- Implemented HTTP transport recorder for testing expensive API calls
- Added PII sanitization for test recordings
- Added regression tests

**No breaking changes** - Internal fix only

## Testing

```bash
source venv/bin/activate
./code_quality_checks.sh

# Run the new tests added in this PR
python -m pytest tests/test_o3_pro_output_text_fix.py -v
python -m pytest tests/test_pii_sanitizer.py -v

# Or run all new tests together
python -m pytest tests/test_o3_pro_output_text_fix.py tests/test_pii_sanitizer.py -v
```

- [x] All checks pass
- [x] Regression tests added:
  - `test_o3_pro_output_text_fix.py` - Validates o3-pro response parsing and HTTP transport recording
  - `test_pii_sanitizer.py` - Ensures API key sanitization

## Code Example

**Before:**
```python
# Incorrect - manual parsing
for content_item in response.output.content:
    if content_item.type == "output_text":
        content = content_item.text
```

**After:**
```python
# Correct - direct field access
content = response.output_text
```

## For Reviewers

- Core fix: `providers/openai_compatible.py` - see `_safe_extract_output_text()` method
- Response parsing: `_generate_with_responses_endpoint()` method now uses the direct field
- Test infrastructure changes don't affect production code
- All test recordings sanitized for security