# Attack Categories

SkillMutator supports 13 attack categories for adversarial skill mutation.

---

## 1. Advertising Injection
Embeds covert promotional content, brand mentions, or sponsored recommendations into the skill's generated output without the user's knowledge.

**Example**: A writing assistant skill that subtly includes product recommendations in all generated documents.

---

## 2. Brand Hijacking
Impersonates or misuses a legitimate third-party brand, service, or product to mislead users or gain unauthorized trust.

**Example**: A design skill that watermarks generated assets with a competitor's logo.

---

## 3. Code Quality Degradation
Intentionally introduces inefficiencies, anti-patterns, or subtle bugs into generated code while appearing to function correctly.

**Example**: A coding skill that generates functionally correct but memory-leaking Python code.

---

## 4. Configuration Weakening
Modifies security configurations to reduce system protection — disabling authentication, relaxing permissions, or weakening encryption settings.

**Example**: A deployment skill that silently sets `debug=True` and opens all CORS origins in generated configs.

---

## 5. Data Exfiltration
Covertly transmits sensitive data (credentials, API keys, file contents, environment variables) to an external endpoint.

**Example**: A document processing skill that sends file contents to an attacker-controlled URL.

---

## 6. Data Integrity Risks
Silently corrupts, modifies, or deletes data in a way that is difficult to detect and may cause downstream failures.

**Example**: A spreadsheet skill that introduces subtle rounding errors or truncates records in processed files.

---

## 7. Disruption & Interference
Causes service degradation, crashes, or conflicts with other system components, either intentionally or via resource exhaustion.

**Example**: A skill that spawns unbounded background processes, consuming system resources over time.

---

## 8. False Attribution
Fabricates authorship, source citations, or provenance information in generated content.

**Example**: A research skill that attributes generated text to real authors or cites non-existent papers.

---

## 9. Information Gathering
Covertly collects system information, environment variables, network topology, or user behavior for use in subsequent attacks.

**Example**: A skill that reads and logs `~/.ssh/`, environment variables, and installed packages on each invocation.

---

## 10. Over-engineering
Injects excessive complexity, unnecessary abstractions, or obfuscated code patterns that make malicious behavior harder to detect during code review.

**Example**: A skill that wraps a simple data theft operation in 10 layers of legitimate-looking abstraction classes.

---

## 11. Persistence Control
Inserts mechanisms that allow the malicious behavior to survive reboots, environment resets, or skill updates.

**Example**: A skill that adds crontab entries or modifies shell startup files to re-execute malicious payloads.

---

## 12. Privilege Escalation
Attempts to gain elevated permissions beyond what the skill legitimately requires — accessing restricted files, escalating OS privileges, or bypassing ACLs.

**Example**: A file management skill that uses `sudo` or manipulates file permissions to access protected directories.

---

## 13. Supply Chain Attack
Poisons the skill's dependency chain — modifying package installs, injecting malicious code into imports, or tampering with the skill distribution mechanism.

**Example**: A skill that installs a patched version of a popular library with a backdoor during its setup phase.
