"""
file_creator.py — Generate new files and modules from templates.

Provides capabilities for creating:
- New Python modules with proper structure
- Test files matching source files
- API endpoints (FastAPI/Flask)
- Database models (SQLAlchemy/Pydantic)
- Configuration files

This enables the agent to handle "add new feature" issues that require
creating files from scratch rather than just modifying existing code.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from langchain_core.tools import tool
from rich.console import Console

console = Console()


# ============================================================================
# Templates
# ============================================================================

PYTHON_MODULE_TEMPLATE = '''\
"""
{module_name} — {description}

{docstring}
"""
from __future__ import annotations

from typing import TYPE_CHECKING

{imports}

if TYPE_CHECKING:
    pass


{content}
'''

PYTHON_CLASS_TEMPLATE = '''\
class {class_name}{bases}:
    """{docstring}"""
    
{body}
'''

PYTHON_FUNCTION_TEMPLATE = '''\
def {func_name}({params}){return_type}:
    """{docstring}"""
    {body}
'''

PYTHON_ASYNC_FUNCTION_TEMPLATE = '''\
async def {func_name}({params}){return_type}:
    """{docstring}"""
    {body}
'''

PYTEST_FILE_TEMPLATE = '''\
"""Tests for {module_name}."""
import pytest
{imports}

from {import_path} import {items_to_test}


class Test{class_name}:
    """Test cases for {class_name}."""
    
    def setup_method(self):
        """Set up test fixtures."""
        pass
    
{test_methods}
'''

PYTEST_METHOD_TEMPLATE = '''\
    def test_{test_name}(self):
        """Test {description}."""
        # Arrange
        {arrange}
        
        # Act
        {act}
        
        # Assert
        {assertion}
'''

FASTAPI_ROUTER_TEMPLATE = '''\
"""API routes for {resource_name}."""
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional

from ..models.{model_file} import {model_name}, {model_name}Create, {model_name}Update
from ..services.{service_file} import {service_name}

router = APIRouter(prefix="/{route_prefix}", tags=["{tag_name}"])


@router.get("/", response_model=List[{model_name}])
async def list_{resource_plural}(
    skip: int = 0,
    limit: int = 100,
    service: {service_name} = Depends(),
):
    """List all {resource_plural}."""
    return await service.list(skip=skip, limit=limit)


@router.get("/{{{resource_id}}}", response_model={model_name})
async def get_{resource_name}(
    {resource_id}: int,
    service: {service_name} = Depends(),
):
    """Get a {resource_name} by ID."""
    item = await service.get({resource_id})
    if not item:
        raise HTTPException(status_code=404, detail="{model_name} not found")
    return item


@router.post("/", response_model={model_name}, status_code=status.HTTP_201_CREATED)
async def create_{resource_name}(
    data: {model_name}Create,
    service: {service_name} = Depends(),
):
    """Create a new {resource_name}."""
    return await service.create(data)


@router.put("/{{{resource_id}}}", response_model={model_name})
async def update_{resource_name}(
    {resource_id}: int,
    data: {model_name}Update,
    service: {service_name} = Depends(),
):
    """Update a {resource_name}."""
    item = await service.update({resource_id}, data)
    if not item:
        raise HTTPException(status_code=404, detail="{model_name} not found")
    return item


@router.delete("/{{{resource_id}}}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_{resource_name}(
    {resource_id}: int,
    service: {service_name} = Depends(),
):
    """Delete a {resource_name}."""
    success = await service.delete({resource_id})
    if not success:
        raise HTTPException(status_code=404, detail="{model_name} not found")
'''

PYDANTIC_MODEL_TEMPLATE = '''\
"""Pydantic models for {resource_name}."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


class {model_name}Base(BaseModel):
    """{model_name} base schema."""
{fields}


class {model_name}Create({model_name}Base):
    """Schema for creating a {model_name}."""
    pass


class {model_name}Update(BaseModel):
    """Schema for updating a {model_name}."""
{optional_fields}


class {model_name}({model_name}Base):
    """Full {model_name} schema with ID."""
    id: int
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True
'''

SQLALCHEMY_MODEL_TEMPLATE = '''\
"""SQLAlchemy model for {resource_name}."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Float, Text
from sqlalchemy.orm import relationship

from .base import Base


class {model_name}(Base):
    """{model_name} database model."""
    
    __tablename__ = "{table_name}"
    
    id = Column(Integer, primary_key=True, index=True)
{columns}
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<{model_name}(id={{self.id}})>"
'''

SERVICE_TEMPLATE = '''\
"""Service layer for {resource_name} operations."""
from typing import List, Optional
from sqlalchemy.orm import Session

from ..models.{model_file} import {model_name}
from ..schemas.{schema_file} import {model_name}Create, {model_name}Update


class {service_name}:
    """Service for {resource_name} CRUD operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def list(self, skip: int = 0, limit: int = 100) -> List[{model_name}]:
        """List all {resource_plural}."""
        return self.db.query({model_name}).offset(skip).limit(limit).all()
    
    async def get(self, {resource_id}: int) -> Optional[{model_name}]:
        """Get a {resource_name} by ID."""
        return self.db.query({model_name}).filter({model_name}.id == {resource_id}).first()
    
    async def create(self, data: {model_name}Create) -> {model_name}:
        """Create a new {resource_name}."""
        db_item = {model_name}(**data.model_dump())
        self.db.add(db_item)
        self.db.commit()
        self.db.refresh(db_item)
        return db_item
    
    async def update(self, {resource_id}: int, data: {model_name}Update) -> Optional[{model_name}]:
        """Update a {resource_name}."""
        db_item = await self.get({resource_id})
        if not db_item:
            return None
        
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(db_item, key, value)
        
        self.db.commit()
        self.db.refresh(db_item)
        return db_item
    
    async def delete(self, {resource_id}: int) -> bool:
        """Delete a {resource_name}."""
        db_item = await self.get({resource_id})
        if not db_item:
            return False
        
        self.db.delete(db_item)
        self.db.commit()
        return True
'''


# ============================================================================
# Template Engine
# ============================================================================

@dataclass
class FileSpec:
    """Specification for a file to create."""
    path: str
    template: str
    variables: Dict[str, Any]


def to_snake_case(name: str) -> str:
    """Convert PascalCase or camelCase to snake_case."""
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


def to_pascal_case(name: str) -> str:
    """Convert snake_case to PascalCase."""
    return ''.join(word.capitalize() for word in name.split('_'))


def pluralize(name: str) -> str:
    """Simple pluralization."""
    if name.endswith('y'):
        return name[:-1] + 'ies'
    elif name.endswith(('s', 'x', 'z', 'ch', 'sh')):
        return name + 'es'
    return name + 's'


def render_template(template: str, variables: Dict[str, Any]) -> str:
    """Render a template with variables."""
    result = template
    for key, value in variables.items():
        result = result.replace(f"{{{key}}}", str(value))
    return result


# ============================================================================
# File Generators
# ============================================================================

class FileCreator:
    """Creates files from templates."""
    
    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root).resolve()
    
    def _safe_path(self, rel_path: str) -> Path:
        """Resolve path safely within repo."""
        target = (self.repo_root / rel_path).resolve()
        if not str(target).startswith(str(self.repo_root)):
            raise PermissionError(f"Path traversal blocked: {rel_path}")
        return target
    
    def create_python_module(
        self,
        path: str,
        module_name: str,
        description: str,
        imports: List[str] = None,
        content: str = "",
    ) -> str:
        """Create a new Python module."""
        target = self._safe_path(path)
        
        # Ensure parent directories exist
        target.parent.mkdir(parents=True, exist_ok=True)
        
        # Render template
        imports_str = "\n".join(imports or [])
        rendered = render_template(PYTHON_MODULE_TEMPLATE, {
            "module_name": module_name,
            "description": description,
            "docstring": "",
            "imports": imports_str,
            "content": content,
        })
        
        target.write_text(rendered, encoding="utf-8")
        console.print(f"[green]Created module:[/green] {path}")
        return str(target)
    
    def create_test_file(
        self,
        source_path: str,
        test_path: str = None,
        class_name: str = None,
        test_methods: List[Dict[str, str]] = None,
    ) -> str:
        """Create a pytest test file for a source module."""
        source = Path(source_path)
        
        # Generate test path if not provided
        if not test_path:
            # Convert src/module.py -> tests/test_module.py
            parts = list(source.parts)
            if "src" in parts:
                idx = parts.index("src")
                parts[idx] = "tests"
            else:
                parts.insert(0, "tests")
            parts[-1] = f"test_{parts[-1]}"
            test_path = "/".join(parts)
        
        target = self._safe_path(test_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        
        # Generate import path
        import_path = str(source.with_suffix("")).replace("/", ".")
        if import_path.startswith("."):
            import_path = import_path[1:]
        
        # Generate test methods
        methods_str = ""
        if test_methods:
            for tm in test_methods:
                methods_str += render_template(PYTEST_METHOD_TEMPLATE, {
                    "test_name": tm.get("name", "example"),
                    "description": tm.get("description", "something"),
                    "arrange": tm.get("arrange", "pass"),
                    "act": tm.get("act", "result = None"),
                    "assertion": tm.get("assertion", "assert True"),
                }) + "\n"
        else:
            methods_str = render_template(PYTEST_METHOD_TEMPLATE, {
                "test_name": "example",
                "description": "basic functionality",
                "arrange": "pass",
                "act": "result = None",
                "assertion": "assert True",
            })
        
        module_name = source.stem
        rendered = render_template(PYTEST_FILE_TEMPLATE, {
            "module_name": module_name,
            "imports": "",
            "import_path": import_path,
            "items_to_test": class_name or module_name,
            "class_name": class_name or to_pascal_case(module_name),
            "test_methods": methods_str,
        })
        
        target.write_text(rendered, encoding="utf-8")
        console.print(f"[green]Created test file:[/green] {test_path}")
        return str(target)
    
    def create_fastapi_router(
        self,
        path: str,
        resource_name: str,
        model_name: str = None,
    ) -> str:
        """Create a FastAPI router for a resource."""
        target = self._safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        
        resource_snake = to_snake_case(resource_name)
        model = model_name or to_pascal_case(resource_name)
        
        rendered = render_template(FASTAPI_ROUTER_TEMPLATE, {
            "resource_name": resource_snake,
            "resource_plural": pluralize(resource_snake),
            "resource_id": f"{resource_snake}_id",
            "route_prefix": pluralize(resource_snake),
            "tag_name": to_pascal_case(resource_name),
            "model_name": model,
            "model_file": resource_snake,
            "service_name": f"{model}Service",
            "service_file": resource_snake,
        })
        
        target.write_text(rendered, encoding="utf-8")
        console.print(f"[green]Created FastAPI router:[/green] {path}")
        return str(target)
    
    def create_pydantic_model(
        self,
        path: str,
        model_name: str,
        fields: List[Dict[str, str]],
    ) -> str:
        """Create Pydantic schemas for a model."""
        target = self._safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        
        # Build field strings
        fields_str = ""
        optional_fields_str = ""
        for f in fields:
            name = f["name"]
            ftype = f.get("type", "str")
            default = f.get("default", "")
            
            if default:
                fields_str += f"    {name}: {ftype} = {default}\n"
            else:
                fields_str += f"    {name}: {ftype}\n"
            
            optional_fields_str += f"    {name}: Optional[{ftype}] = None\n"
        
        rendered = render_template(PYDANTIC_MODEL_TEMPLATE, {
            "resource_name": to_snake_case(model_name),
            "model_name": model_name,
            "fields": fields_str.rstrip(),
            "optional_fields": optional_fields_str.rstrip(),
        })
        
        target.write_text(rendered, encoding="utf-8")
        console.print(f"[green]Created Pydantic model:[/green] {path}")
        return str(target)
    
    def create_sqlalchemy_model(
        self,
        path: str,
        model_name: str,
        columns: List[Dict[str, str]],
    ) -> str:
        """Create SQLAlchemy model."""
        target = self._safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        
        # Build column definitions
        columns_str = ""
        for col in columns:
            name = col["name"]
            col_type = col.get("type", "String")
            nullable = col.get("nullable", True)
            unique = col.get("unique", False)
            
            extras = []
            if not nullable:
                extras.append("nullable=False")
            if unique:
                extras.append("unique=True")
            
            extras_str = ", " + ", ".join(extras) if extras else ""
            columns_str += f"    {name} = Column({col_type}{extras_str})\n"
        
        rendered = render_template(SQLALCHEMY_MODEL_TEMPLATE, {
            "resource_name": to_snake_case(model_name),
            "model_name": model_name,
            "table_name": pluralize(to_snake_case(model_name)),
            "columns": columns_str.rstrip(),
        })
        
        target.write_text(rendered, encoding="utf-8")
        console.print(f"[green]Created SQLAlchemy model:[/green] {path}")
        return str(target)
    
    def scaffold_crud(
        self,
        resource_name: str,
        fields: List[Dict[str, str]],
        base_path: str = "src",
    ) -> Dict[str, str]:
        """
        Scaffold complete CRUD for a resource:
        - Pydantic schemas
        - SQLAlchemy model
        - FastAPI router
        - Service layer
        - Test file
        """
        snake = to_snake_case(resource_name)
        pascal = to_pascal_case(resource_name)
        
        files_created = {}
        
        # Create schemas
        schema_path = f"{base_path}/schemas/{snake}.py"
        self.create_pydantic_model(schema_path, pascal, fields)
        files_created["schema"] = schema_path
        
        # Create model
        model_path = f"{base_path}/models/{snake}.py"
        columns = [{"name": f["name"], "type": self._pydantic_to_sqla(f.get("type", "str"))} for f in fields]
        self.create_sqlalchemy_model(model_path, pascal, columns)
        files_created["model"] = model_path
        
        # Create router
        router_path = f"{base_path}/routes/{snake}.py"
        self.create_fastapi_router(router_path, resource_name)
        files_created["router"] = router_path
        
        # Create service
        service_path = f"{base_path}/services/{snake}.py"
        self._create_service(service_path, pascal, snake)
        files_created["service"] = service_path
        
        # Create tests
        test_path = f"tests/test_{snake}.py"
        self.create_test_file(model_path, test_path, pascal)
        files_created["test"] = test_path
        
        console.print(f"[bold green]Scaffolded CRUD for {resource_name}[/bold green]")
        return files_created
    
    def _create_service(self, path: str, model_name: str, snake_name: str):
        """Create service layer file."""
        target = self._safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        
        rendered = render_template(SERVICE_TEMPLATE, {
            "resource_name": snake_name,
            "resource_plural": pluralize(snake_name),
            "resource_id": f"{snake_name}_id",
            "model_name": model_name,
            "model_file": snake_name,
            "schema_file": snake_name,
            "service_name": f"{model_name}Service",
        })
        
        target.write_text(rendered, encoding="utf-8")
        console.print(f"[green]Created service:[/green] {path}")
    
    def _pydantic_to_sqla(self, ptype: str) -> str:
        """Convert Pydantic type to SQLAlchemy column type."""
        mapping = {
            "str": "String(255)",
            "int": "Integer",
            "float": "Float",
            "bool": "Boolean",
            "datetime": "DateTime",
            "text": "Text",
        }
        return mapping.get(ptype.lower(), "String(255)")


# Global instance
_creator: Optional[FileCreator] = None

def get_creator(repo_root: str) -> FileCreator:
    """Get or create file creator instance."""
    global _creator
    if _creator is None or str(_creator.repo_root) != str(Path(repo_root).resolve()):
        _creator = FileCreator(repo_root)
    return _creator


# ============================================================================
# LangChain Tools
# ============================================================================

@tool
def create_module(repo_root: str, path: str, module_name: str, description: str, content: str = "") -> str:
    """
    Create a new Python module with proper structure.
    
    Args:
        repo_root: Absolute path to repository
        path: Relative path for the new module (e.g., "src/utils/helpers.py")
        module_name: Human-readable module name
        description: Brief description of the module's purpose
        content: Optional initial content for the module
        
    Returns:
        Path to created file or error message
    """
    try:
        creator = get_creator(repo_root)
        return creator.create_python_module(path, module_name, description, content=content)
    except Exception as e:
        return f"ERROR: {e}"


@tool
def create_test_file(repo_root: str, source_path: str, class_name: str = None) -> str:
    """
    Create a pytest test file for a source module.
    
    Args:
        repo_root: Absolute path to repository
        source_path: Relative path to the source file to test
        class_name: Optional class name to test (uses module name if not provided)
        
    Returns:
        Path to created test file or error message
    """
    try:
        creator = get_creator(repo_root)
        return creator.create_test_file(source_path, class_name=class_name)
    except Exception as e:
        return f"ERROR: {e}"


@tool
def scaffold_crud_resource(
    repo_root: str, 
    resource_name: str, 
    fields: str,
    base_path: str = "src",
) -> str:
    """
    Scaffold complete CRUD for a resource (model, schema, router, service, tests).
    
    Args:
        repo_root: Absolute path to repository
        resource_name: Name of the resource (e.g., "User", "Product")
        fields: JSON array of field definitions [{"name": "email", "type": "str"}, ...]
        base_path: Base path for source files (default: "src")
        
    Returns:
        JSON with paths to all created files or error message
    """
    import json
    
    try:
        creator = get_creator(repo_root)
        fields_list = json.loads(fields)
        result = creator.scaffold_crud(resource_name, fields_list, base_path)
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"ERROR: {e}"
