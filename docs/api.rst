API Reference
=============

This page documents the public API of Agenter.

AutonomousCodingAgent
---------------------

The main entry point for using Agenter.

.. autoclass:: agenter.AutonomousCodingAgent
   :members:
   :undoc-members:
   :show-inheritance:

Data Models
-----------

Request and response models for the coding agent.

CodingRequest
~~~~~~~~~~~~~

.. autoclass:: agenter.CodingRequest
   :members:
   :undoc-members:
   :show-inheritance:

CodingResult
~~~~~~~~~~~~

.. autoclass:: agenter.CodingResult
   :members:
   :undoc-members:
   :show-inheritance:

CodingEvent
~~~~~~~~~~~

.. autoclass:: agenter.CodingEvent
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: agenter.CodingEventType
   :members:
   :undoc-members:
   :show-inheritance:

Budget
~~~~~~

.. autoclass:: agenter.Budget
   :members:
   :undoc-members:
   :show-inheritance:

Tools
-----

Tool protocol and decorator for custom tools.

Tool Protocol
~~~~~~~~~~~~~

.. autoclass:: agenter.Tool
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: agenter.FunctionTool
   :members:
   :undoc-members:
   :show-inheritance:

tool Decorator
~~~~~~~~~~~~~~

.. autofunction:: agenter.tool

ToolResult
~~~~~~~~~~

.. autoclass:: agenter.ToolResult
   :members:
   :undoc-members:
   :show-inheritance:

File System
-----------

File operations and path resolution utilities.

.. autoclass:: agenter.FileOperations
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: agenter.PathResolver
   :members:
   :undoc-members:
   :show-inheritance:

Runtime
-------

Budget tracking and file tracing utilities.

.. autoclass:: agenter.BudgetMeter
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: agenter.FileTracer
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: agenter.Tracer
   :members:
   :undoc-members:
   :show-inheritance:

Validators
----------

Post-execution validators.

.. autoclass:: agenter.SyntaxValidator
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: agenter.ValidationResult
   :members:
   :undoc-members:
   :show-inheritance:

Errors
------

Exception classes raised by Agenter.

.. autoclass:: agenter.AgenterError
   :members:
   :show-inheritance:

.. autoclass:: agenter.BackendError
   :members:
   :show-inheritance:

.. autoclass:: agenter.BudgetExceededError
   :members:
   :show-inheritance:

.. autoclass:: agenter.ConfigurationError
   :members:
   :show-inheritance:

.. autoclass:: agenter.PathSecurityError
   :members:
   :show-inheritance:

.. autoclass:: agenter.ToolExecutionError
   :members:
   :show-inheritance:

.. autoclass:: agenter.ValidationError
   :members:
   :show-inheritance:

Enums
-----

.. autoclass:: agenter.Verbosity
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: agenter.CodingStatus
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: agenter.ToolError
   :members:
   :undoc-members:
   :show-inheritance:

.. autoclass:: agenter.ToolErrorCode
   :members:
   :undoc-members:
   :show-inheritance:

Logging
-------

.. autofunction:: agenter.configure_logging
