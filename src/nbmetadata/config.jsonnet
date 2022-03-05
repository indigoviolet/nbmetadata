function(user_config={})
  local base_config = {
    nbmake_timeout_300: {
      _top: true,
      metadata: { execution: { timeout: 300 } },
    },
    nbmake_raises: {
      custom: { metadata: { tags: ['raises-exception'] } },
    },
    nbmake_skip: {
      custom: { metadata: { tags: ['skip-execution'] } },
    },
  };
  base_config + user_config
