module.exports = function (eleventyConfig) {
  eleventyConfig.addPassthroughCopy("data");
  eleventyConfig.addPassthroughCopy("scrapers");
  eleventyConfig.addPassthroughCopy("styles.css");
  eleventyConfig.addPassthroughCopy("app.js");
  eleventyConfig.addPassthroughCopy("Circular-badge-logo.png");
  eleventyConfig.addPassthroughCopy("eos-logo.png");
eleventyConfig.addPassthroughCopy("src/assets");

  return {
    dir: {
      input: "src",
      output: "_site"
    }
  };
};
