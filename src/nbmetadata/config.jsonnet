function(user_config={})
  local base_config = {
    nbmake_timeout_300: {
      _top: true,
      execution: { timeout: 300 },
    },
    nbmake_raises: {
      tags: ['raises-exception'],
    },
    nbmake_skip: {
      tags: ['skip-execution'],
    },
  };
  base_config + user_config
