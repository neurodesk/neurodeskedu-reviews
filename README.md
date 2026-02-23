:warning: **Please don't submit bug reports for Neurodesk and NeurodeskEDU here. Instead please submit a discussion in [the Neurodesk repo](https://github.com/orgs/neurodesk/discussions)** :warning:

# Reviews for NeurodeskEDU

This repository tracks peer reviews for [NeurodeskEDU](https://neurodesk.org/edu/) notebooks and pages.

Each notebook carries a unique Review ID (UUID) in its metadata. A corresponding GitHub Issue here tracks the review lifecycle. Labels drive the workflow — assigning reviewers, posting checklists, recording commit SHAs, and triggering badge rebuilds are all automated via GitHub Actions.

### Review lifecycle

| Phase | Label | What happens |
|-------|-------|-------------|
| **Queued** | `review:queued` | Issue created, UUID generated, metadata injected |
| **In progress** | `review:in-progress` | Reviewer checklist posted |
| **Accepted** | `reviewed` | Commit SHA recorded, badge turns green |
| **Minor update** | `review:refresh` | SHA re-stamped without full re-review |

## Code of Conduct

In order to have a more open and welcoming community, Neurodesk adheres to a code of conduct adapted from the [Contributor Covenant](http://contributor-covenant.org) code of conduct.

Please adhere to this code of conduct in any interactions you have in the Neurodesk community. It is strictly enforced on all official Neurodesk repositories, the Neurodesk website, and resources. If you encounter someone violating these terms, please let the team know (mail.neurodesk@gmail.com) and we will address it as soon as possible.
