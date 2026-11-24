// IrisCreateViewController.m - Post creation interface implementation
#import "IrisCreateViewController.h"
#import "IrisTheme.h"
#import "IrisData.h"
#import "IrisTabBarController.h"

@interface IrisCreateViewController () <UITextViewDelegate, UITextFieldDelegate>

@property (nonatomic, strong) UIScrollView *scrollView;
@property (nonatomic, strong) UIView *headerBar;
@property (nonatomic, strong) UILabel *titleLabel;
@property (nonatomic, strong) UIButton *shareTopButton;

// Media Preview
@property (nonatomic, strong) UIView *previewContainer;
@property (nonatomic, strong) UIImageView *previewImageView;
@property (nonatomic, strong) UIButton *galleryButton;
@property (nonatomic, strong) UIButton *cameraButton;
@property (nonatomic, strong) NSString *selectedImageKey;

// Inputs
@property (nonatomic, strong) UITextView *captionTextView;
@property (nonatomic, strong) UILabel *captionPlaceholder;
@property (nonatomic, strong) UITextField *locationField;
@property (nonatomic, strong) UISegmentedControl *audienceControl;
@property (nonatomic, strong) UIButton *shareMainButton;

@end

@implementation IrisCreateViewController

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.selectedImageKey = @"post_new_created";
    
    [self setupHeader];
    [self setupScrollView];
    [self setupFormContent];
    
    [[NSNotificationCenter defaultCenter] addObserver:self
                                             selector:@selector(handleThemeChanged:)
                                                 name:IrisThemeDidChangeNotification
                                               object:nil];
}

- (void)dealloc {
    [[NSNotificationCenter defaultCenter] removeObserver:self];
}

- (void)setupHeader {
    CGFloat topSafe = 36.0;
    CGFloat headerH = topSafe + 48.0;
    
    self.headerBar = [[UIView alloc] initWithFrame:CGRectMake(0, 0, self.view.bounds.size.width, headerH)];
    self.headerBar.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    self.headerBar.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    
    self.titleLabel = [[UILabel alloc] initWithFrame:CGRectMake(16, topSafe + 8, 160, 32)];
    self.titleLabel.text = @"New Post";
    self.titleLabel.font = [UIFont systemFontOfSize:22 weight:UIFontWeightBold];
    self.titleLabel.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    [self.headerBar addSubview:self.titleLabel];
    
    self.shareTopButton = [UIButton buttonWithType:UIButtonTypeCustom];
    self.shareTopButton.frame = CGRectMake(self.view.bounds.size.width - 80, topSafe + 8, 64, 32);
    self.shareTopButton.autoresizingMask = UIViewAutoresizingFlexibleLeftMargin;
    [self.shareTopButton setTitle:@"Share" forState:UIControlStateNormal];
    [self.shareTopButton setTitleColor:[[IrisTheme sharedTheme] accentVioletColor] forState:UIControlStateNormal];
    self.shareTopButton.titleLabel.font = [UIFont systemFontOfSize:15 weight:UIFontWeightBold];
    [self.shareTopButton addTarget:self action:@selector(handleShareTapped) forControlEvents:UIControlEventTouchUpInside];
    [self.headerBar addSubview:self.shareTopButton];
    
    UIView *line = [[UIView alloc] initWithFrame:CGRectMake(0, headerH - 0.5, self.view.bounds.size.width, 0.5)];
    line.backgroundColor = [[IrisTheme sharedTheme] dividerColor];
    line.autoresizingMask = UIViewAutoresizingFlexibleWidth;
    [self.headerBar addSubview:line];
    
    [self.view addSubview:self.headerBar];
}

- (void)setupScrollView {
    CGFloat topSafe = 36.0;
    CGFloat headerH = topSafe + 48.0;
    CGFloat bottomH = 64.0;
    
    self.scrollView = [[UIScrollView alloc] initWithFrame:CGRectMake(0, headerH, self.view.bounds.size.width, self.view.bounds.size.height - headerH - bottomH)];
    self.scrollView.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    self.scrollView.alwaysBounceVertical = YES;
    self.scrollView.keyboardDismissMode = UIScrollViewKeyboardDismissModeOnDrag;
    [self.view addSubview:self.scrollView];
}

- (void)setupFormContent {
    CGFloat w = self.view.bounds.size.width;
    CGFloat pad = 16.0;
    CGFloat y = 16.0;
    
    // 1. Media Preview Box
    CGFloat previewH = 220.0;
    self.previewContainer = [[UIView alloc] initWithFrame:CGRectMake(pad, y, w - pad * 2, previewH)];
    self.previewContainer.backgroundColor = [[IrisTheme sharedTheme] cardBackgroundColor];
    self.previewContainer.layer.cornerRadius = 14.0;
    self.previewContainer.layer.masksToBounds = YES;
    
    self.previewImageView = [[UIImageView alloc] initWithFrame:self.previewContainer.bounds];
    self.previewImageView.contentMode = UIViewContentModeScaleAspectFill;
    self.previewImageView.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    self.previewImageView.image = [IrisData imageForKey:self.selectedImageKey
                                                   size:CGSizeMake(w - pad * 2, previewH)
                                                  title:@"Shibuya Twilight"
                                               subtitle:@"Iris High-Dynamic Capture"];
    [self.previewContainer addSubview:self.previewImageView];
    
    // Action overlay buttons on preview
    self.galleryButton = [UIButton buttonWithType:UIButtonTypeCustom];
    self.galleryButton.frame = CGRectMake(12, previewH - 44, 96, 32);
    self.galleryButton.backgroundColor = [UIColor colorWithWhite:0 alpha:0.7];
    self.galleryButton.layer.cornerRadius = 8.0;
    [self.galleryButton setTitle:@"🖼️ Gallery" forState:UIControlStateNormal];
    [self.galleryButton setTitleColor:[UIColor whiteColor] forState:UIControlStateNormal];
    self.galleryButton.titleLabel.font = [UIFont systemFontOfSize:12 weight:UIFontWeightMedium];
    [self.galleryButton addTarget:self action:@selector(selectMockPhoto) forControlEvents:UIControlEventTouchUpInside];
    [self.previewContainer addSubview:self.galleryButton];
    
    self.cameraButton = [UIButton buttonWithType:UIButtonTypeCustom];
    self.cameraButton.frame = CGRectMake(116, previewH - 44, 96, 32);
    self.cameraButton.backgroundColor = [UIColor colorWithWhite:0 alpha:0.7];
    self.cameraButton.layer.cornerRadius = 8.0;
    [self.cameraButton setTitle:@"📷 Camera" forState:UIControlStateNormal];
    [self.cameraButton setTitleColor:[UIColor whiteColor] forState:UIControlStateNormal];
    self.cameraButton.titleLabel.font = [UIFont systemFontOfSize:12 weight:UIFontWeightMedium];
    [self.cameraButton addTarget:self action:@selector(selectMockCamera) forControlEvents:UIControlEventTouchUpInside];
    [self.previewContainer addSubview:self.cameraButton];
    
    [self.scrollView addSubview:self.previewContainer];
    y += previewH + 16.0;
    
    // 2. Caption Input Box
    UIView *captionCard = [[UIView alloc] initWithFrame:CGRectMake(pad, y, w - pad * 2, 96)];
    captionCard.backgroundColor = [[IrisTheme sharedTheme] cardBackgroundColor];
    captionCard.layer.cornerRadius = 12.0;
    captionCard.layer.masksToBounds = YES;
    
    self.captionTextView = [[UITextView alloc] initWithFrame:CGRectMake(8, 6, captionCard.bounds.size.width - 16, 84)];
    self.captionTextView.backgroundColor = [UIColor clearColor];
    self.captionTextView.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    self.captionTextView.font = [UIFont systemFontOfSize:14];
    self.captionTextView.delegate = self;
    [captionCard addSubview:self.captionTextView];
    
    self.captionPlaceholder = [[UILabel alloc] initWithFrame:CGRectMake(14, 14, captionCard.bounds.size.width - 28, 20)];
    self.captionPlaceholder.text = @"Write a thoughtful caption, stories, #tags...";
    self.captionPlaceholder.textColor = [[IrisTheme sharedTheme] mutedTextColor];
    self.captionPlaceholder.font = [UIFont systemFontOfSize:14];
    [captionCard addSubview:self.captionPlaceholder];
    
    [self.scrollView addSubview:captionCard];
    y += 96.0 + 14.0;
    
    // 3. Location Input
    UIView *locCard = [[UIView alloc] initWithFrame:CGRectMake(pad, y, w - pad * 2, 48)];
    locCard.backgroundColor = [[IrisTheme sharedTheme] cardBackgroundColor];
    locCard.layer.cornerRadius = 12.0;
    
    UILabel *locIcon = [[UILabel alloc] initWithFrame:CGRectMake(12, 12, 24, 24)];
    locIcon.text = @"📍";
    locIcon.font = [UIFont systemFontOfSize:16];
    [locCard addSubview:locIcon];
    
    self.locationField = [[UITextField alloc] initWithFrame:CGRectMake(40, 6, locCard.bounds.size.width - 50, 36)];
    self.locationField.placeholder = @"Add location (e.g. Kyoto, Japan)";
    self.locationField.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    self.locationField.font = [UIFont systemFontOfSize:14];
    self.locationField.delegate = self;
    [locCard addSubview:self.locationField];
    
    [self.scrollView addSubview:locCard];
    y += 48.0 + 14.0;
    
    // 4. Audience Selector
    UILabel *audLabel = [[UILabel alloc] initWithFrame:CGRectMake(pad + 4, y, w - pad * 2, 18)];
    audLabel.text = @"AUDIENCE";
    audLabel.font = [UIFont systemFontOfSize:11 weight:UIFontWeightBold];
    audLabel.textColor = [[IrisTheme sharedTheme] secondaryTextColor];
    [self.scrollView addSubview:audLabel];
    y += 24.0;
    
    self.audienceControl = [[UISegmentedControl alloc] initWithItems:@[@"Public", @"Close Friends", @"Private"]];
    self.audienceControl.frame = CGRectMake(pad, y, w - pad * 2, 36);
    self.audienceControl.selectedSegmentIndex = 0;
    self.audienceControl.selectedSegmentTintColor = [[IrisTheme sharedTheme] accentVioletColor];
    [self.scrollView addSubview:self.audienceControl];
    y += 36.0 + 24.0;
    
    // 5. Main Share Button
    self.shareMainButton = [UIButton buttonWithType:UIButtonTypeCustom];
    self.shareMainButton.frame = CGRectMake(pad, y, w - pad * 2, 50);
    self.shareMainButton.layer.cornerRadius = 14.0;
    self.shareMainButton.backgroundColor = [[IrisTheme sharedTheme] accentVioletColor];
    [self.shareMainButton setTitle:@"Share to Iris Feed ✨" forState:UIControlStateNormal];
    [self.shareMainButton setTitleColor:[UIColor whiteColor] forState:UIControlStateNormal];
    self.shareMainButton.titleLabel.font = [UIFont systemFontOfSize:16 weight:UIFontWeightBold];
    [self.shareMainButton addTarget:self action:@selector(handleShareTapped) forControlEvents:UIControlEventTouchUpInside];
    [self.scrollView addSubview:self.shareMainButton];
    
    y += 50.0 + 40.0;
    self.scrollView.contentSize = CGSizeMake(w, y);
}

#pragma mark - Mock Selection

- (void)selectMockPhoto {
    NSArray *mockKeys = @[@"post_arch2", @"post_neon2", @"post_mountain2", @"post_coffee2", @"post_tokyo1", @"post_scotland1"];
    NSInteger randIdx = arc4random_uniform((uint32_t)mockKeys.count);
    self.selectedImageKey = mockKeys[randIdx];
    
    self.previewImageView.image = [IrisData imageForKey:self.selectedImageKey
                                                   size:self.previewContainer.bounds.size
                                                  title:@"Imported from Gallery"
                                               subtitle:@"Iris ProRAW Format"];
}

- (void)selectMockCamera {
    self.selectedImageKey = @"post_camera_capture";
    self.previewImageView.image = [IrisData imageForKey:self.selectedImageKey
                                                   size:self.previewContainer.bounds.size
                                                  title:@"Camera Shot"
                                               subtitle:@"HakiOS Sensor Fixture"];
}

#pragma mark - Text View Delegate

- (void)textViewDidChange:(UITextView *)textView {
    self.captionPlaceholder.hidden = (textView.text.length > 0);
}

- (BOOL)textFieldShouldReturn:(UITextField *)textField {
    [textField resignFirstResponder];
    return YES;
}

#pragma mark - Share Action

- (void)handleShareTapped {
    NSString *caption = [self.captionTextView.text stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
    NSString *location = [self.locationField.text stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
    NSString *aud = [self.audienceControl titleForSegmentAtIndex:self.audienceControl.selectedSegmentIndex];
    
    // Add locally to IrisData
    [[IrisData sharedData] addNewPostWithCaption:caption
                                        location:location
                                        audience:aud
                                        imageKey:self.selectedImageKey];
    
    // Reset inputs
    self.captionTextView.text = @"";
    self.captionPlaceholder.hidden = NO;
    self.locationField.text = @"";
    [self.view endEditing:YES];
    
    // Show confirmation dialog & switch to Home feed
    UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Post Shared! 🎉"
                                                                   message:@"Your post is now live at the top of your Iris feed."
                                                            preferredStyle:UIAlertControllerStyleAlert];
    __weak typeof(self) weakSelf = self;
    [alert addAction:[UIAlertAction actionWithTitle:@"View on Feed" style:UIAlertActionStyleDefault handler:^(UIAlertAction * _Nonnull action) {
        if ([weakSelf.parentViewController isKindOfClass:[IrisTabBarController class]]) {
            [(IrisTabBarController *)weakSelf.parentViewController switchToTab:IrisTabItemHome];
        }
    }]];
    [self presentViewController:alert animated:YES completion:nil];
}

- (void)handleThemeChanged:(NSNotification *)note {
    self.view.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.headerBar.backgroundColor = [[IrisTheme sharedTheme] mainBackgroundColor];
    self.titleLabel.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    self.previewContainer.backgroundColor = [[IrisTheme sharedTheme] cardBackgroundColor];
    self.captionTextView.textColor = [[IrisTheme sharedTheme] primaryTextColor];
    self.locationField.textColor = [[IrisTheme sharedTheme] primaryTextColor];
}

@end
