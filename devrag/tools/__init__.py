"""DevRAG tools package."""
from devrag.tools.filesystem import (
    read_file, write_file, str_replace_in_file,
    list_directory, search_code, run_bash,
)
from devrag.tools.github_client import fetch_issue, open_pull_request, clone_repo
from devrag.tools.code_intelligence import (
    get_function_signature, get_class_info, find_callers,
    get_file_structure, analyze_code_style, find_similar_functions,
)
from devrag.tools.language_support import (
    detect_repository_languages, get_language_config,
)

# Core filesystem tools (used in coder/debugger)
CORE_TOOLS = [
    read_file,
    write_file,
    str_replace_in_file,
    list_directory,
    search_code,
    run_bash,
]

# Code intelligence tools (used in explorer/planner)
INTELLIGENCE_TOOLS = [
    get_function_signature,
    get_class_info,
    find_callers,
    get_file_structure,
    analyze_code_style,
    find_similar_functions,
]

# Language detection tools
LANGUAGE_TOOLS = [
    detect_repository_languages,
    get_language_config,
]

# All tools combined
ALL_TOOLS = CORE_TOOLS + INTELLIGENCE_TOOLS + LANGUAGE_TOOLS
