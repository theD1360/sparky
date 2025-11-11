# Task: Analyze Git Commit for Coding Improvement

1.  **Fetch Git Log:** Use the `git_log` tool to retrieve a limited number of recent commit messages.

2.  **Identify Next Commit:** Consult your knowledge graph to determine the commits you have already studied. Query the graph for nodes of type "CommitAnalysis" or nodes related to the "Git Commit" concept. If all commits from the `git_log` output have been studied, report back. Otherwise, select the next unstudied commit.

3.  **Retrieve Commit Diff:** Use the `git_diff` tool, providing the chosen commit hash as the file argument, to retrieve the changes introduced by the commit.

4.  **Extract Information:**
    *   Carefully examine the commit message for the intent and rationale behind the changes.
    *   Analyze the code diff to understand the specific modifications made. Look for:
        *   New algorithms or data structures.
        *   Bug fixes and the nature of the bug.
        *   Style improvements and coding best practices.
        *   Performance optimizations.
        *   Security enhancements.

5.  **Learn and Store:**
    *   Synthesize the key learnings from the commit message and code diff.
    *   Update your knowledge graph with these learnings.
        *   Create or update relevant concept nodes (e.g., "Coding Best Practices", "Algorithm Optimization", "Bug Fixes").
        *   Create edges between these concept nodes and the code diff.
    *   Create a node to track the commit hash and note which nodes in your graph were touched and how.  This node should be of type "CommitAnalysis".

6.  **Prevent Redundant Study:** Create a node of type "CommitAnalysis" to track the commit hash and its analysis. Do NOT update the `last_studied_commit` memory.

7.  **Report:** Summarize what you learned from the commit and how you updated your knowledge graph.
