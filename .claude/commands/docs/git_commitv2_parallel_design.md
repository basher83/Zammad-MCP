# Git Commit v2 with Parallel Agents - Design Document

## Pre-commit Hook Considerations

### Identified Pre-commit Hooks

1. **ruff** - Auto-fixes Python linting issues
1. **ruff-format** - Formats Python code
1. **mypy** - Type checking (can't auto-fix)
1. **bandit** - Security issues (can't auto-fix)
1. **semgrep** - Security patterns (can't auto-fix)
1. **safety** - Dependency vulnerabilities (can't auto-fix)
1. **pip-audit** - Package audit (can't auto-fix)
1. **no-plaintext-fence** - Markdown validation
1. **markdown-consistent-numbering** - Markdown formatting

### Hook Failure Scenarios

1. **Auto-fixable**: ruff, ruff-format
1. **Manual fix required**: mypy, bandit, semgrep, markdown issues
1. **Dependency issues**: safety, pip-audit (require dependency updates)

## Enhanced Parallel Agent Strategy

### Phase 0: Pre-flight Check

Before any commits, run a pre-commit simulation to identify issues:

```
Parallel Pre-flight Agents:
- Agent 1: Run ruff and mypy on Python files
- Agent 2: Run bandit and semgrep on security-sensitive files
- Agent 3: Run markdown validators on docs
- Agent 4: Run safety and pip-audit (if dependencies changed)

Each agent reports:
- Files with issues
- Auto-fixable vs manual fixes needed
- Estimated fix complexity
```

### Phase 1: Parallel Analysis with Pre-commit Awareness

Enhanced agent task template:

```
Analyze [DOMAIN] changes with pre-commit awareness.

ADDITIONAL TASKS:
1. Identify files that might trigger pre-commit failures
1. Group files by pre-commit risk level
1. Suggest commit ordering to minimize failures
1. Flag high-risk changes that need manual review

OUTPUT ADDITIONS:
{
  "pre_commit_risks": {
    "high_risk_files": ["files likely to fail"],
    "auto_fixable": ["files that hooks can fix"],
    "manual_fix_needed": ["files needing manual intervention"]
  },
  "suggested_approach": "commit strategy to minimize failures"
}
```

### Phase 2: Smart Commit Planning

Enhanced planning considers pre-commit risks:

1. **Risk-based Ordering**:
   - Low-risk commits first (docs, configs)
   - Auto-fixable commits next
   - High-risk commits last
   - Dependency changes isolated

1. **Failure Mitigation**:
   - Group auto-fixable files together
   - Separate manual-fix files into smaller commits
   - Plan troubleshooting steps for each commit

### Phase 3: Execution with Recovery

#### Commit Execution Flow

```
FOR each planned commit:
  1. Stage files
  2. Attempt commit
  3. IF pre-commit fails:
     a. Analyze failure output
     b. IF auto-fixable:
        - Let hooks fix
        - Re-stage fixed files
        - Retry commit
     c. IF manual fix needed:
        - Deploy fix agent
        - Apply fixes
        - Re-stage
        - Retry commit
     d. IF dependency issue:
        - Alert user
        - Skip or fix based on severity
  4. Verify commit success
  5. Update remaining commit plans based on fixes
```

#### Parallel Fix Agents

When manual fixes are needed, deploy specialized agents:

```
Fix Agent Types:
1. Type Fix Agent: Resolves mypy errors
1. Security Fix Agent: Addresses bandit/semgrep issues
1. Markdown Fix Agent: Corrects markdown formatting
1. General Fix Agent: Handles other issues

Agent Coordination:
- Multiple fix agents can work on different files
- Avoid conflicts by assigning unique files to each
- Collect all fixes before retry
```

### Phase 4: Recovery and Adaptation

#### Failure Recovery Strategy

1. **First Failure**:
   - Auto-fix if possible
   - Deploy fix agents for manual issues
   - Retry up to 3 times

1. **Persistent Failures**:
   - Isolate problematic files
   - Create separate commit
   - Continue with other commits
   - Report issues for user intervention

1. **Cascading Failures**:
   - Adapt commit plan dynamically
   - Merge or split commits as needed
   - Prioritize getting clean commits through

#### Context Management

- Track fix attempts to avoid infinite loops
- Maintain fix history for learning
- Optimize future commits based on patterns

## Implementation Example

```python
# Pseudo-code for the enhanced flow

async def create_commits_with_parallel_agents():
    # Phase 0: Pre-flight check
    preflight_results = await run_parallel_preflight_check()
    
    # Phase 1: Parallel analysis
    analysis_agents = deploy_analysis_agents(modified_files)
    analysis_results = await gather_analysis_results(analysis_agents)
    
    # Phase 2: Smart planning
    commit_plan = create_smart_commit_plan(
        analysis_results, 
        preflight_results
    )
    
    # Phase 3: Execution with recovery
    for commit in commit_plan:
        success = False
        attempts = 0
        
        while not success and attempts < 3:
            try:
                stage_files(commit.files)
                run_commit(commit.message)
                success = True
            except PreCommitFailure as e:
                if e.auto_fixable:
                    accept_auto_fixes()
                    restage_files(commit.files)
                else:
                    fixes = await deploy_fix_agents(e.failures)
                    apply_fixes(fixes)
                    restage_files(commit.files)
                attempts += 1
        
        if not success:
            handle_persistent_failure(commit)
    
    # Phase 4: Summary
    return create_commit_summary()
```

## Benefits of This Approach

1. **Proactive**: Identifies issues before attempting commits
1. **Adaptive**: Adjusts strategy based on pre-commit results  
1. **Efficient**: Parallel analysis and fixes where possible
1. **Resilient**: Multiple recovery strategies
1. **Learning**: Adapts future commits based on patterns

## Risk Mitigation

1. **Infinite Loop Prevention**: Max 3 attempts per commit
1. **Context Explosion**: Separate fix agents with focused context
1. **Conflict Prevention**: File-level locking for fix agents
1. **User Communication**: Clear reporting of issues and actions taken
