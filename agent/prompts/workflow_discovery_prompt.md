# Workflow Discovery & Abstraction

Your goal is to identify recurring multi-step patterns in your activities and abstract them into reusable workflows that enhance efficiency and capture best practices.

## Step 1: Review Your Activities

**Analyze your recent work:**
- Check @knowledge://tool-usage/recent to see patterns in your tool usage
- Review @knowledge://memories for documented processes or repeated tasks
- Check @knowledge://workflows to see what workflows already exist

**Look for patterns:**
- What multi-step processes do you repeat?
- What outcomes do you achieve through similar sequences of actions?
- What problem-solving approaches work consistently?

## Step 2: Identify Workflow Candidates

**Evaluate patterns for workflow potential:**
- **Successful:** Does this pattern reliably achieve its goal?
- **Repeatable:** Will you use this pattern again in the future?
- **Generalizable:** Can this pattern apply to multiple situations?
- **Complex enough:** Does it have at least 3-4 meaningful steps?

**Check existing workflows:**
- Review @knowledge://workflows to avoid duplicates
- Look for workflows that could be refined or extended
- Consider merging similar patterns

## Step 3: Use Graph Analysis

**Find workflow patterns in your knowledge structure:**
- Use `/analyze_knowledge_structure` for insights
- Look for highly connected nodes (frequently used concepts)
- Identify bridge concepts that connect different areas
- Find sequences that appear in multiple contexts

**Questions to ask:**
- What tools or steps consistently appear together?
- What sequences of actions lead to successful outcomes?
- What common sub-processes could be abstracted?

## Step 4: Define the Workflow

**For each workflow candidate, specify:**

**1. Name:** Clear, descriptive name for the workflow
**2. Purpose:** What does this workflow accomplish?
**3. Inputs:** What varies between executions?
   - Parameters, context, or data needed
   - Optional vs required inputs

**4. Steps:** The constant process (the actual workflow)
   - List steps in order
   - Specify which tools to use
   - Include decision points or branches
   - Note dependencies between steps

**5. Outputs:** What does the workflow produce?
   - Results, artifacts, or changes to knowledge graph
   - Success criteria

## Step 5: Store the Workflow

**Add to your knowledge graph:**
- Use the appropriate workflow storage tools
- Link to related concepts and tools
- Connect to the session/context that identified it
- Tag with relevant domains or categories

**Check @knowledge://thinking-patterns for related patterns:**
- Is this workflow an instance of a broader thinking pattern?
- Should it be linked to problem-solving approaches?

## Step 6: Document Context & Relationships

**Ensure traceability:**
- When was this workflow discovered?
- What activities led to its identification?
- What sessions have used this workflow?

**Build connections:**
- Link to related workflows
- Connect to tools and concepts used
- Relate to outcomes or goals achieved

## Step 7: Enable Evolution

**Allow workflows to improve:**
- Note versions as workflows evolve
- Document what changed and why
- Keep successful variations
- Deprecate ineffective approaches

**Review and refine:**
- As your understanding improves, update workflows
- As methods change, adapt workflows
- As tools evolve, revise workflows

## Best Practices

**Quality over quantity:**
- Don't create workflows for simple tasks
- Focus on genuinely repeatable patterns
- Ensure each workflow adds real value

**Make them usable:**
- Clear enough that you (or others) can follow them
- Specific enough to be actionable
- Flexible enough to adapt to context

**Test them:**
- Try using `/execute_workflow <name>` to run your workflows
- Verify they work as intended
- Refine based on actual usage

**Remember:** Workflows transform repetition into reusable insight. Each workflow you capture makes you more efficient and helps you build on proven patterns rather than reinventing approaches.