qx.Class.define("gosa.test.data.TemplateRegistryTest",
{
  extend : qx.dev.unit.TestCase,

  members :
  {
    testAddAndGetTemplates : function() {
      var registry = gosa.data.TemplateRegistry.getInstance();

      this.assertFunction(registry.addTemplate);

      this.assertArrayEquals([], registry.getTemplates("foobar"));

      registry.addTemplate("myExtension", "{}");
      var templates = registry.getTemplates("myExtension");
      this.assertArray(templates);
      this.assertTrue(templates.length === 1);
      this.assertObject(templates[0]);

      registry.addTemplate("myExtension", "{}");
      templates = registry.getTemplates("myExtension");
      this.assertArray(templates);
      this.assertTrue(templates.length === 2);
      this.assertObject(templates[0]);
      this.assertObject(templates[1]);
    },

    testAddMultipleTemplatesAtOnce : function() {
      var registry = gosa.data.TemplateRegistry.getInstance();

      registry.assertFunction(registry.addTemplates);
      registry.addTemplates("myMultipleExtension", ["{}", "{}"]);
      var templates = registry.getTemplates("myMultipleExtension");
      this.assertArray(templates);
      this.assertTrue(templates.length === 2);
      this.assertObject(templates[0]);
      this.assertObject(templates[1]);
    },

    testHasTemplate : function() {
      var registry = gosa.data.TemplateRegistry.getInstance();

      registry.assertFunction(registry.hasTemplate);
      this.assertFalse(registry.hasTemplate("unkownExtension"));

      registry.addTemplate("myExistingExtension", "{}");
      this.assertTrue(registry.hasTemplate("myExistingExtension"));
    },

    testAddDialogTemplate : function() {
      var registry = gosa.data.TemplateRegistry.getInstance();

      registry.assertFunction(registry.addDialogTemplate);
      registry.assertFunction(registry.getDialogTemplate);

      registry.assertNull(registry.getDialogTemplate("unkownTemplate"));

      registry.addDialogTemplate("dialog1", "{}");
      this.assertObject(registry.getDialogTemplate("dialog1"));

      registry.addDialogTemplate("dialog2", "{}");
      this.assertObject(registry.getDialogTemplate("dialog1"));
      this.assertObject(registry.getDialogTemplate("dialog2"));
    },

    testAddMultipleDialogTemplates : function() {
      var registry = gosa.data.TemplateRegistry.getInstance();
      registry.assertFunction(registry.addDialogTemplates);

      registry.assertNull(registry.getDialogTemplate("unkownTemplate"));

      registry.addDialogTemplates({
        "dialogMulti1" : "{}",
        "dialogMulti2" : "{}"
      });
      this.assertObject(registry.getDialogTemplate("dialogMulti1"));
      this.assertObject(registry.getDialogTemplate("dialogMulti2"));
    }
  }
});
