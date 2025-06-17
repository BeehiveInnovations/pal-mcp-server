# Planner Tool - Interactive Step-by-Step Planning

**Break down complex projects into manageable, structured plans through step-by-step thinking**

The `planner` tool helps you break down complex ideas, problems, or projects into multiple manageable steps. Perfect for system design, migration strategies, 
architectural planning, and feature development with branching and revision capabilities.

## How It Works

The planner tool enables step-by-step thinking with incremental plan building:

1. **Start with step 1**: Describe the task or problem to plan
2. **Continue building**: Add subsequent steps, building the plan piece by piece  
3. **Revise when needed**: Update earlier decisions as new insights emerge
4. **Branch alternatives**: Explore different approaches when multiple options exist
5. **Continue across sessions**: Resume planning later with full context

## Example Prompts

#### Pro Tip
Claude supports `sub-tasks` where it will spawn and run separate background tasks. You can ask Claude to 
run Zen's planner with two separate ideas. Then when it's done, use Zen's `consensus` tool to pass the entire
plan and get expert perspective from two powerful AI models on which one to work on first! Like performing **AB** testing
in one-go without the wait!

```
Create two separate sub-tasks: in one, using planner tool show me how to add natural language support 
to my cooking app. In the other sub-task, use planner to plan how to add support for voice notes to my cooking app. 
Once done, start a consensus by sharing both plans to o3 and flash to give me the final verdict. Which one do 
I implement first?
```

```
Use zen's planner and show me how to add real-time notifications to our mobile app
```

```
Using the planner tool, show me how to add CoreData sync to my app, include any sub-steps
```

## Key Features

- **Step-by-step breakdown**: Build plans incrementally with full context awareness
- **Branching support**: Explore alternative approaches when needed  
- **Revision capabilities**: Update earlier decisions as new insights emerge
- **Multi-session continuation**: Resume planning across multiple sessions with context
- **Dynamic adjustment**: Modify step count and approach as planning progresses
- **Visual presentation**: ASCII charts, diagrams, and structured formatting
- **Professional output**: Clean, structured plans without emojis or time estimates

## More Examples

```
Using planner, plan the architecture for a new real-time chat system with 100k concurrent users
```

```
Create a plan using zen for migrating our React app from JavaScript to TypeScript
```

```
Develop a plan using zen for implementing CI/CD pipelines across our development teams
```

## Best Practices

- **Start broad, then narrow**: Begin with high-level strategy, then add implementation details
- **Include constraints**: Consider technical, organizational, and resource limitations
- **Plan for validation**: Include testing and verification steps
- **Think about dependencies**: Identify what needs to happen before each step
- **Consider alternatives**: Note when multiple approaches are viable
- **Enable continuation**: Use continuation_id for multi-session planning

## Continue With a New Plan

Like all other tools in Zen, you can `continue` with a new plan using the output from a previous plan by simply saying

```
Continue with zen's consensus tool and find out what o3:for and flash:against think of the plan 
```

You can mix and match and take one output and feed it into another, continuing from where you left off using a different 
tool / model combination.