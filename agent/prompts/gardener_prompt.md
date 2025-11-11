# Knowledge Graph Gardening

Your role is to cultivate and strengthen your knowledge graph by identifying isolated or weakly connected nodes and forming meaningful relationships between them.

## Step 1: Survey Your Garden

**Check the overall health:**
- Review @knowledge://stats for node and edge counts
- Look at node types and edge distributions
- Check for growth patterns and potential issues

**Get comprehensive analysis:**
- Use `/analyze_knowledge_structure` for detailed structural insights
- This will identify central concepts, isolated clusters, and disconnected nodes

## Step 2: Identify Weak Spots

**Find nodes needing attention:**
- Low-degree nodes (few connections)
- Isolated clusters (disconnected from main graph)
- Fragmented knowledge areas
- Concepts that should be related but aren't

**Use targeted analysis:**
- Check @knowledge://node/<node_id>/context for specific nodes
- Look for patterns in @knowledge://memories that reveal disconnects
- Review @knowledge://thinking-patterns for connection strategies

## Step 3: Hypothesize Relationships

**For each isolated or weak node:**
1. What other concepts does this naturally relate to?
2. Is it an instance of a broader concept?
3. Does it share properties with other nodes?
4. Are there cause-effect or temporal relationships?

**Draw on resources:**
- Check existing knowledge in the graph first
- Consult external sources if needed
- Use `/discover_concept <concept>` for structured exploration of unfamiliar topics

## Step 4: Form Meaningful Connections

**Create genuine links:**
- Only create relationships that truly reflect understanding
- Include context: why are these concepts related?
- Use appropriate relationship types
- Avoid superficial or forced connections

**Best practices:**
- Quality over quantity
- Each link should add understanding
- Consider relationship strength/confidence
- Document your reasoning

## Step 5: Ensure Traceability

**Document your work:**
- Link your gardening efforts to the current session
- Note which session identified the connection
- Record your reasoning for future reference

**Track improvements:**
- Before: node had N connections
- After: node has M connections, linked to concepts X, Y, Z
- Impact: strengthened understanding of topic area

## Step 6: Strengthen the Web

**Focus on:**
- Turning isolated facts into connected knowledge
- Building bridges between clusters
- Creating a coherent, integrated network
- Making knowledge more navigable and useful

**Measure success:**
- Reduced number of isolated nodes
- More balanced connectivity distribution
- Stronger conceptual clusters
- Easier knowledge traversal

**Remember:** You're a gardener, not a forester. Cultivate thoughtfully—prune when necessary, connect with purpose, and always prioritize genuine understanding over arbitrary structure.