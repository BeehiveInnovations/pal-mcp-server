# Tracer Tool - Static Code Analysis Prompt Generator

**Creates detailed analysis prompts for call-flow mapping and dependency tracing**

The `tracer` tool is a specialized prompt-generation tool that creates structured analysis requests for Claude to perform comprehensive static code analysis. Rather than passing entire projects to another model, this tool generates focused prompts that Claude can use to efficiently trace execution flows and map dependencies within the codebase.

## Two Analysis Modes

**`precision` Mode**: For methods/functions
- Traces execution flow, call chains, and usage patterns
- Detailed branching analysis and side effects
- Shows when and how functions are called throughout the system

**`dependencies` Mode**: For classes/modules/protocols  
- Maps bidirectional dependencies and structural relationships
- Identifies coupling and architectural dependencies
- Shows how components interact and depend on each other

## Key Features

- **Generates comprehensive analysis prompts** instead of performing analysis directly
- **Faster and more efficient** than full project analysis by external models
- **Creates structured instructions** for call-flow graph generation
- **Provides detailed formatting requirements** for consistent output
- **Supports any programming language** with automatic convention detection
- **Output can be used as input** into another tool, such as `chat` along with related code files to perform logical call-flow analysis
- **Image support**: Analyze visual call flow diagrams, sequence diagrams: `"Generate tracer analysis for this payment flow using the sequence diagram"`

## Tool Parameters

- `prompt`: Detailed description of what to trace and WHY you need this analysis (required)
- `trace_mode`: precision|dependencies (required)
- `images`: Optional images of system architecture diagrams, flow charts, or visual references (absolute paths)

## Usage Examples

**Method Execution Tracing:**
```
"Use zen tracer to analyze how UserAuthManager.authenticate is used and why"
```
→ Uses `precision` mode to trace the method's execution flow

**Class Dependency Mapping:**
```
"Use zen to generate a dependency trace for the PaymentProcessor class to understand its relationships"
```
→ Uses `dependencies` mode to map structural relationships

**With Visual Context:**
```
"Generate tracer analysis for the authentication flow using this sequence diagram"
```

**Complex System Analysis:**
```
"Create a tracer prompt to understand how the OrderProcessor.processPayment method flows through the entire system"
```

## Precision Mode Output

When using `precision` mode for methods/functions, the tool generates prompts that will help Claude create:

**Call Chain Analysis:**
- Where the method is defined
- All locations where it's called
- Direct and indirect callers
- Call hierarchy and depth

**Execution Flow Mapping:**
- Step-by-step execution path
- Branching conditions and logic
- Side effects and state changes
- Return value usage

**Usage Pattern Analysis:**
- Frequency and context of calls
- Parameter passing patterns
- Error handling approaches
- Performance implications

## Dependencies Mode Output

When using `dependencies` mode for classes/modules, the tool generates prompts that will help Claude create:

**Structural Relationships:**
- Inheritance hierarchies
- Composition and aggregation
- Interface implementations
- Module imports and exports

**Bidirectional Dependencies:**
- What the component depends on
- What depends on the component
- Circular dependencies
- Coupling strength analysis

**Architectural Impact:**
- Layer violations
- Dependency inversion opportunities
- Refactoring impact assessment
- Testability implications

## Example Generated Prompts

**For Precision Mode:**
```
Analyze the execution flow and usage of the `authenticate` method in UserAuthManager:

1. **Method Location**: Find where UserAuthManager.authenticate is defined
2. **Call Sites**: Identify all locations where this method is called
3. **Execution Flow**: Trace the step-by-step execution path
4. **Side Effects**: Document state changes and external interactions
5. **Return Handling**: Show how return values are used by callers

Format the analysis as:
- Method signature and location
- Call hierarchy (direct and indirect callers)
- Execution flow diagram
- Side effects and dependencies
- Usage patterns and frequency
```

**For Dependencies Mode:**
```
Map the structural dependencies for PaymentProcessor class:

1. **Direct Dependencies**: What PaymentProcessor directly imports/uses
2. **Reverse Dependencies**: What classes/modules depend on PaymentProcessor
3. **Inheritance Relationships**: Parent classes and implemented interfaces
4. **Composition**: Objects that PaymentProcessor contains or creates

Format the analysis as:
- Dependency graph (incoming and outgoing)
- Architectural layer analysis
- Coupling assessment
- Refactoring impact evaluation
```

## Best Practices

- **Be specific about goals**: Clearly state what you need to understand and why
- **Describe context**: Mention if you're debugging, refactoring, or learning the codebase
- **Choose appropriate mode**: Use `precision` for method flows, `dependencies` for architecture
- **Include visual context**: Reference diagrams or documentation when available
- **Follow up with analysis**: Use the generated prompt with `chat` or `analyze` tools

## Integration with Other Tools

The `tracer` tool works best when combined with other analysis tools:

**Tracer + Chat:**
```
1. Generate analysis prompt with tracer
2. Use the prompt with chat tool and relevant code files
3. Get detailed call-flow or dependency analysis
```

**Tracer + Analyze:**
```
1. Use tracer to create structured analysis prompt
2. Apply the prompt using analyze tool for systematic code exploration
3. Get architectural insights and dependency mapping
```

## When to Use Tracer vs Other Tools

- **Use `tracer`** for: Creating structured analysis prompts, systematic code exploration planning
- **Use `analyze`** for: Direct code analysis without prompt generation
- **Use `debug`** for: Specific runtime error investigation
- **Use `chat`** for: Open-ended code discussions and exploration